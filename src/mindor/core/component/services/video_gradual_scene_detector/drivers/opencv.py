from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from mindor.dsl.schema.component import VideoGradualSceneDetectorComponentConfig, VideoGradualSceneDetectorDriverType
from mindor.dsl.schema.action import VideoGradualSceneDetectorActionConfig
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VideoGradualSceneDetectorDriver, register_video_gradual_scene_detector_driver
from ..base import ComponentActionContext
from .common import VideoGradualSceneDetectorAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

_BLOCK_GRID = (6, 8)           # (cols, rows) — passed to cv2.resize as dsize so x then y
_LOW_THUMBNAIL_SIZE = (12, 16) # (w, h) low-resolution thumbnail for the first-pass scan

class OpenCvVideoGradualSceneDetectorAction(VideoGradualSceneDetectorAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        downsample_width        = await context.render_scalar(self.config.downsample_width, int)
        window_lengths_raw      = await context.render_variable(self.config.window_lengths)
        plateau_share           = await context.render_scalar(self.config.plateau_share, float)
        min_changed_share       = await context.render_scalar(self.config.min_changed_share, float)
        endpoint_min_std        = await context.render_scalar(self.config.endpoint_min_std, float)
        endpoint_diff_threshold = await context.render_scalar(self.config.endpoint_diff_threshold, float)
        motion_warp_threshold   = await context.render_scalar(self.config.motion_warp_threshold, float)

        if not 16 <= downsample_width <= 4096:
            raise ValueError(f"'downsample_width' must be between 16 and 4096, got {downsample_width}")

        if not window_lengths_raw:
            raise ValueError("'window_lengths' must contain at least one entry")

        window_lengths = tuple(parse_time(value) if isinstance(value, str) else float(value) for value in window_lengths_raw)

        if any(value <= 0.0 for value in window_lengths):
            raise ValueError(f"'window_lengths' values must be positive, got {window_lengths}")

        if not 0.0 <= plateau_share <= 1.0:
            raise ValueError(f"'plateau_share' must be between 0.0 and 1.0, got {plateau_share}")

        if not 0.0 <= min_changed_share <= 1.0:
            raise ValueError(f"'min_changed_share' must be between 0.0 and 1.0, got {min_changed_share}")

        if endpoint_min_std < 0.0:
            raise ValueError(f"'endpoint_min_std' must be non-negative, got {endpoint_min_std}")

        if endpoint_diff_threshold < 0.0:
            raise ValueError(f"'endpoint_diff_threshold' must be non-negative, got {endpoint_diff_threshold}")

        if not 0.0 < motion_warp_threshold <= 1.0:
            raise ValueError(f"'motion_warp_threshold' must be in (0.0, 1.0], got {motion_warp_threshold}")

        return {
            "downsample_width":        downsample_width,
            "window_lengths":          window_lengths,
            "plateau_share":           plateau_share,
            "min_changed_share":       min_changed_share,
            "endpoint_min_std":        endpoint_min_std,
            "endpoint_diff_threshold": endpoint_diff_threshold,
            "motion_warp_threshold":   motion_warp_threshold,
        }

    async def _detect(
        self,
        frames: ImageArrayValue,
        frame_rate: float,
        known_boundaries: Optional[ArrayValue],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        frames              = await frames.collect()
        known_boundaries = [ int(value) for value in (await known_boundaries.collect() if isinstance(known_boundaries, ArrayValue) else known_boundaries) ] if known_boundaries is not None else []

        def _detect_gradual() -> List[Dict[str, Any]]:
            import numpy as np
            import cv2

            frame_count = len(frames)

            if frame_count < 8:
                return []

            thumbnails = [ self._luma_thumbnail(frame, params["downsample_width"]) for frame in frames ]
            low_thumbnails = [ cv2.resize(thumbnail, _LOW_THUMBNAIL_SIZE, interpolation=cv2.INTER_AREA) for thumbnail in thumbnails ]

            found: List[Tuple[int, int, int]] = []

            for window_length in params["window_lengths"]:
                window_length = max(4, int(round(window_length * frame_rate)))
                pad = max(3, window_length // 2)
                step = max(1, window_length // 5)

                for start in range(pad, frame_count - window_length - pad, step):
                    end = start + window_length

                    if any(start - pad <= boundary <= end + pad for boundary in known_boundaries):
                        continue

                    if any(found_start - pad <= start + window_length // 2 <= found_end + pad for found_start, found_end, _ in found):
                        continue

                    end_distance = float(np.abs(low_thumbnails[start] - low_thumbnails[end]).mean())

                    if end_distance < params["endpoint_diff_threshold"]:
                        continue

                    before_distance = float(np.abs(low_thumbnails[start - pad] - low_thumbnails[start]).mean())
                    after_distance  = float(np.abs(low_thumbnails[end + pad] - low_thumbnails[end]).mean())
                    plateau_budget  = params["plateau_share"] * end_distance

                    if before_distance > plateau_budget or after_distance > plateau_budget:
                        continue

                    block_mad = self._block_diff(thumbnails[start], thumbnails[end])
                    changed_share = float((block_mad > max(10.0, 0.5 * float(np.median(block_mad)))).mean())

                    if changed_share < params["min_changed_share"]:
                        continue

                    if self._same_structure(thumbnails[start], thumbnails[end]):
                        continue

                    if self._motion_explains(thumbnails[start], thumbnails[end], params["motion_warp_threshold"]):
                        continue

                    if min(float(thumbnails[start].std()), float(thumbnails[end].std())) < params["endpoint_min_std"]:
                        continue

                    progression = self._progress(thumbnails, start, end, start - pad, end + pad)

                    if float(progression[:pad].max()) > 0.3 or float(progression[-pad:].min()) < 0.7:
                        continue

                    tight_start, tight_end, boundary = self._tight(progression, start - pad)
                    outer_pad    = max(2, (tight_end - tight_start) // 2)
                    outer_before = max(0, tight_start - outer_pad)
                    outer_after  = min(frame_count - 1, tight_end + outer_pad)

                    tight_distance        = self._mean_abs_diff(thumbnails[tight_start], thumbnails[tight_end])
                    tight_before_distance = self._mean_abs_diff(thumbnails[outer_before], thumbnails[tight_start])
                    tight_after_distance  = self._mean_abs_diff(thumbnails[outer_after], thumbnails[tight_end])
                    tight_plateau_budget  = params["plateau_share"] * tight_distance

                    if tight_before_distance > tight_plateau_budget or tight_after_distance > tight_plateau_budget:
                        continue

                    found.append((tight_start, tight_end, boundary))

            return [
                {
                    "start_frame":    tight_start,
                    "end_frame":      tight_end,
                    "boundary_frame": boundary,
                    "frame_rate":     frame_rate,
                }
                for tight_start, tight_end, boundary in found
            ]

        return await self._run_in_executor(_detect_gradual)

    def _luma_thumbnail(self, frame: PILImage.Image, downsample_width: int):
        """PIL frame -> BT.601 luma float32 thumbnail, resized with OpenCV's INTER_AREA
        (small motion averages out at this scale)."""
        import numpy as np
        import cv2

        luma = np.asarray(frame.convert("L"), dtype=np.float32)
        height, width = luma.shape

        if width == 0 or height == 0:
            return np.zeros((1, 1), dtype=np.float32)

        if width > downsample_width:
            height = max(1, int(round(height * downsample_width / width)))
            luma = cv2.resize(luma, (downsample_width, height), interpolation=cv2.INTER_AREA)

        return luma

    def _mean_abs_diff(self, a: Any, b: Any) -> float:
        import numpy as np

        return float(np.abs(a - b).mean())

    def _block_diff(self, a: Any, b: Any, shift: int = 2) -> Any:
        """Per-block mean |a - b|, taking the best of a few small shifts so that
        ordinary motion in the shot does not count as a different picture."""
        import numpy as np
        import cv2

        height, width = a.shape
        best_diff = None

        for dx, dy in ((0, 0), (shift, 0), (-shift, 0), (0, shift), (0, -shift)):
            shifted = np.roll(b, (dy, dx), axis=(0, 1))
            diff = cv2.resize(
                np.abs(a - shifted)[shift:height - shift, shift:width - shift],
                _BLOCK_GRID,
                interpolation=cv2.INTER_AREA,
            )
            best_diff = diff if best_diff is None else np.minimum(best_diff, diff)

        return best_diff

    def _motion_explains(self, a: Any, b: Any, tolerance: float) -> bool:
        """True when b is (mostly) a warped copy of a (zoom / pan / subject motion):
        optical-flow warping b back onto a leaves less than `tolerance` of the
        original residual, so the apparent change is movement rather than new content."""
        import numpy as np
        import cv2

        a_uint8 = np.clip(a, 0, 255).astype(np.uint8)
        b_uint8 = np.clip(b, 0, 255).astype(np.uint8)
        optical_flow = cv2.calcOpticalFlowFarneback(a_uint8, b_uint8, None, 0.5, 3, 9, 3, 5, 1.1, 0)

        height, width = a_uint8.shape
        grid_x, grid_y = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
        warped = cv2.remap(b_uint8, grid_x + optical_flow[..., 0], grid_y + optical_flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        margin = 4
        before_warp_residual = float(np.abs(b_uint8.astype(np.float32) - a_uint8.astype(np.float32))[margin:-margin, margin:-margin].mean())
        after_warp_residual  = float(np.abs(warped.astype(np.float32) - a_uint8.astype(np.float32))[margin:-margin, margin:-margin].mean())

        return after_warp_residual < tolerance * before_warp_residual

    def _same_structure(self, a: Any, b: Any) -> bool:
        """Two frames show the same scene under different light when block by block
        the detail still lines up once brightness is taken out."""
        import numpy as np

        height, width = a.shape
        block_h = max(4, height // _BLOCK_GRID[1])
        block_w = max(4, width // _BLOCK_GRID[0])
        matched_blocks = total_blocks = 0

        for y in range(0, height - block_h + 1, block_h):
            for x in range(0, width - block_w + 1, block_w):
                block_a = a[y:y + block_h, x:x + block_w]
                block_b = b[y:y + block_h, x:x + block_w]
                std_a, std_b = float(block_a.std()), float(block_b.std())

                if std_a < 4.0 or std_b < 4.0:
                    continue

                total_blocks += 1
                correlation = float(((block_a - block_a.mean()) * (block_b - block_b.mean())).mean() / (std_a * std_b))

                if correlation > 0.6:
                    matched_blocks += 1

        return total_blocks >= 6 and matched_blocks / total_blocks > 0.5

    def _progress(self, thumbnails: List[Any], start: int, end: int, lo: int, hi: int) -> Any:
        """For frames lo..hi: 0 = the picture at frame `start`, 1 = the picture at frame `end`."""
        import numpy as np

        start_anchor, end_anchor = thumbnails[start], thumbnails[end]
        progression = np.empty(hi - lo + 1, dtype=np.float32)

        for index, frame_index in enumerate(range(lo, hi + 1)):
            frame = thumbnails[frame_index]
            dist_to_start = float(np.abs(frame - start_anchor).mean())
            dist_to_end   = float(np.abs(frame - end_anchor).mean())
            progression[index] = dist_to_start / (dist_to_start + dist_to_end + 1e-6)

        return progression

    def _tight(self, progress: Any, lo: int) -> Tuple[int, int, int]:
        """(last frame still the old picture, first frame fully the new one,
        frame where the new one takes over) — all offsets relative to `lo`."""
        import numpy as np

        half = int(np.argmax(progress >= 0.5))
        start = half

        while start > 0 and progress[start - 1] > 0.12:
            start -= 1

        end = half

        while end < len(progress) - 1 and progress[end] < 0.88:
            end += 1

        return lo + max(0, start - 1), lo + end, lo + half

@register_video_gradual_scene_detector_driver(VideoGradualSceneDetectorDriverType.OPENCV)
class OpenCvVideoGradualSceneDetectorDriver(VideoGradualSceneDetectorDriver):
    def __init__(self, id: str, config: VideoGradualSceneDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "numpy", "opencv-python" ]

    async def _run(
        self,
        action: VideoGradualSceneDetectorActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await OpenCvVideoGradualSceneDetectorAction(action).run(context)
