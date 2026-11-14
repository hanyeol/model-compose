from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from mindor.dsl.schema.component import VideoFrameAnalyzerComponentConfig, VideoFrameAnalyzerDriverType
from mindor.dsl.schema.action import VideoFrameAnalyzerActionConfig, OpenCvVideoFrameAnalyzerMetric
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VideoFrameAnalyzerDriver, register_video_frame_analyzer_driver
from ..base import ComponentActionContext
from .common import VideoFrameAnalyzerAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

# 24 / 25 fps content transcoded to 30 fps leaves a 4- or 5-frame duplicate
# pattern; 24 -> 60 leaves a 1- or 2-frame pattern. Anything outside this
# table is reported as "irregular" rather than a known pulldown.
_PULLDOWN_TABLE = (
    ("24->30", range(4, 6)),
    ("25->30", range(5, 7)),
    ("24->60", range(1, 3)),
)

class OpenCvVideoFrameAnalyzerAction(VideoFrameAnalyzerAction):
    async def _resolve_params(self, metric: OpenCvVideoFrameAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        if metric == OpenCvVideoFrameAnalyzerMetric.MOVING_PAIRS:
            analysis_width         = await context.render_scalar(self.config.analysis_width, int)
            change_threshold       = await context.render_scalar(self.config.change_threshold, float)
            moving_share_threshold = await context.render_scalar(self.config.moving_share_threshold, float)

            if not 16 <= analysis_width <= 4096:
                raise ValueError(f"'analysis_width' must be between 16 and 4096, got {analysis_width}")

            if change_threshold < 0.0:
                raise ValueError(f"'change_threshold' must be non-negative, got {change_threshold}")

            if not 0.0 <= moving_share_threshold <= 1.0:
                raise ValueError(f"'moving_share_threshold' must be between 0.0 and 1.0, got {moving_share_threshold}")

            return {
                "analysis_width":         analysis_width,
                "change_threshold":       change_threshold,
                "moving_share_threshold": moving_share_threshold,
            }

        if metric == OpenCvVideoFrameAnalyzerMetric.DUPLICATE:
            analysis_width      = await context.render_scalar(self.config.analysis_width, int)
            duplicate_threshold = await context.render_scalar(self.config.duplicate_threshold, float)
            max_period          = await context.render_scalar(self.config.max_period, int)

            if not 16 <= analysis_width <= 4096:
                raise ValueError(f"'analysis_width' must be between 16 and 4096, got {analysis_width}")

            if duplicate_threshold < 0.0:
                raise ValueError(f"'duplicate_threshold' must be non-negative, got {duplicate_threshold}")

            if not 2 <= max_period <= 32:
                raise ValueError(f"'max_period' must be between 2 and 32, got {max_period}")

            return {
                "analysis_width":      analysis_width,
                "duplicate_threshold": duplicate_threshold,
                "max_period":          max_period,
            }

        if metric == OpenCvVideoFrameAnalyzerMetric.SHARPNESS:
            analysis_width = await context.render_scalar(self.config.analysis_width, int)
            max_period     = await context.render_scalar(self.config.max_period, int)

            if not 16 <= analysis_width <= 4096:
                raise ValueError(f"'analysis_width' must be between 16 and 4096, got {analysis_width}")

            if not 2 <= max_period <= 32:
                raise ValueError(f"'max_period' must be between 2 and 32, got {max_period}")

            return {
                "analysis_width": analysis_width,
                "max_period":     max_period,
            }

        raise ValueError(f"Unsupported video frame metric: {metric}")

    async def _analyze(
        self,
        metric: OpenCvVideoFrameAnalyzerMetric,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if metric == OpenCvVideoFrameAnalyzerMetric.MOVING_PAIRS:
            return await self._analyze_moving_pairs(frames, frame_rate, params, cancellation_token)

        if metric == OpenCvVideoFrameAnalyzerMetric.DUPLICATE:
            return await self._analyze_duplicate(frames, frame_rate, params, cancellation_token)

        if metric == OpenCvVideoFrameAnalyzerMetric.SHARPNESS:
            return await self._analyze_sharpness(frames, frame_rate, params, cancellation_token)

        raise ValueError(f"Unsupported video frame metric: {metric}")

    async def _analyze_moving_pairs(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_moving_pairs() -> Dict[str, Any]:
            import numpy as np
            import cv2

            moving_pixel_shares: List[float] = []
            previous_luma = None

            for frame in collected:
                luma = self._thumb_luma(frame, params["analysis_width"])

                if previous_luma is not None:
                    changed_pixels = cv2.absdiff(luma, previous_luma) >= params["change_threshold"]
                    moving_pixel_shares.append(float(changed_pixels.mean()))

                previous_luma = luma

            pair_count = len(moving_pixel_shares)

            if pair_count == 0:
                return {
                    "moving_pair_ratio":       0.0,
                    "moving_pair_count":       0,
                    "pair_count":              0,
                    "mean_changed_pixel_share": 0.0,
                    "max_changed_pixel_share":  0.0,
                    "change_threshold":        params["change_threshold"],
                    "moving_share_threshold":  params["moving_share_threshold"],
                    "frame_count":             len(collected),
                    "frame_rate":              frame_rate,
                    "analysis_width":          params["analysis_width"],
                }

            moving_pixel_shares = np.asarray(moving_pixel_shares, dtype=np.float32)
            moving_pair_count = int((moving_pixel_shares >= params["moving_share_threshold"]).sum())

            return {
                "moving_pair_ratio":        moving_pair_count / pair_count,
                "moving_pair_count":        moving_pair_count,
                "pair_count":               pair_count,
                "mean_changed_pixel_share": float(moving_pixel_shares.mean()),
                "max_changed_pixel_share":  float(moving_pixel_shares.max()),
                "change_threshold":         params["change_threshold"],
                "moving_share_threshold":   params["moving_share_threshold"],
                "frame_count":              len(collected),
                "frame_rate":               frame_rate,
                "analysis_width":           params["analysis_width"],
            }

        return await self._run_in_executor(_analyze_moving_pairs)

    async def _analyze_duplicate(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_duplicate() -> Dict[str, Any]:
            import numpy as np
            import cv2

            # For each adjacent pair, 1 = duplicate / 0 = different. Autocorrelation
            # of this binary signal reveals pulldown cadence (e.g. 24 -> 30 fps
            # repeats every 5th frame, so the duplicate mask has a period-5 peak).
            duplicate_mask: List[int] = []
            previous_luma = None

            for frame in collected:
                luma = self._thumb_luma(frame, params["analysis_width"])

                if previous_luma is not None:
                    duplicate_mask.append(int(float(cv2.absdiff(luma, previous_luma).mean()) < params["duplicate_threshold"]))

                previous_luma = luma

            pair_count = len(duplicate_mask)
            if pair_count == 0:
                return {
                    "dup_ratio":      0.0,
                    "dup_count":      0,
                    "pair_count":     0,
                    "dup_period":     None,
                    "dup_regularity": 0.0,
                    "pulldown":       None,
                    "duplicate_threshold": params["duplicate_threshold"],
                    "max_period":          params["max_period"],
                    "frame_count":   len(collected),
                    "frame_rate":    frame_rate,
                    "analysis_width": params["analysis_width"],
                }

            duplicate_mask = np.asarray(duplicate_mask, dtype=np.float32)
            dup_count = int(duplicate_mask.sum())

            # Autocorrelation of the zero-mean duplicate mask. Lag k = how many
            # frames apart two duplicates sit. The best lag with the strongest
            # peak is the pulldown period.
            if dup_count >= 2:
                dup_period, dup_regularity = self._strongest_period(duplicate_mask, params["max_period"])
            else:
                dup_period, dup_regularity = None, 0.0

            pulldown = _classify_pulldown(dup_period, dup_count / pair_count) if dup_period else None

            return {
                "dup_ratio":           dup_count / pair_count,
                "dup_count":           dup_count,
                "pair_count":          pair_count,
                "dup_period":          dup_period,
                "dup_regularity":      dup_regularity,
                "pulldown":            pulldown,
                "duplicate_threshold": params["duplicate_threshold"],
                "max_period":          params["max_period"],
                "frame_count":         len(collected),
                "frame_rate":          frame_rate,
                "analysis_width":      params["analysis_width"],
            }

        return await self._run_in_executor(_analyze_duplicate)

    async def _analyze_sharpness(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_sharpness() -> Dict[str, Any]:
            import numpy as np
            import cv2

            # Laplacian variance per frame as a sharpness proxy. Frame
            # interpolation introduces a periodic sharpness dip (the synthetic
            # frames are softer than the originals), which autocorrelation
            # exposes as a short-lag peak.
            sharpness_series: List[float] = []

            for frame in collected:
                luma = self._thumb_luma(frame, params["analysis_width"])
                laplacian = cv2.Laplacian(luma, cv2.CV_32F)
                sharpness_series.append(float(laplacian.var()))

            frame_count = len(sharpness_series)

            if frame_count < 2:
                return {
                    "sharpness_mean":   0.0,
                    "sharpness_std":    0.0,
                    "sharp_alt":        0.0,
                    "sharp_period":     None,
                    "sharp_period_ac":  0.0,
                    "frame_count":      frame_count,
                    "frame_rate":       frame_rate,
                    "max_period":       params["max_period"],
                    "analysis_width":   params["analysis_width"],
                }

            sharpness_series = np.asarray(sharpness_series, dtype=np.float32)
            sharpness_mean = float(sharpness_series.mean())

            # `sharp_alt` is the share of adjacent sharpness pairs that dip or
            # peak — a proxy for "sharpness oscillates between frames".
            sharpness_diff = np.diff(sharpness_series)
            sign_flips = int(((sharpness_diff[:-1] * sharpness_diff[1:]) < 0).sum()) if len(sharpness_diff) >= 2 else 0
            sharp_alt = sign_flips / (len(sharpness_diff) - 1) if len(sharpness_diff) >= 2 else 0.0

            sharp_period, sharp_period_ac = self._strongest_period(sharpness_series, params["max_period"])

            return {
                "sharpness_mean":  sharpness_mean,
                "sharpness_std":   float(sharpness_series.std()),
                "sharp_alt":       sharp_alt,
                "sharp_period":    sharp_period,
                "sharp_period_ac": sharp_period_ac,
                "frame_count":     frame_count,
                "frame_rate":      frame_rate,
                "max_period":      params["max_period"],
                "analysis_width":  params["analysis_width"],
            }

        return await self._run_in_executor(_analyze_sharpness)

    def _thumb_luma(self, frame: "PILImage.Image", analysis_width: int):
        """PIL frame -> BT.601 luma float32 thumbnail, resized with OpenCV's INTER_AREA
        (faster than Pillow for the sizes this analyzer works with)."""
        import numpy as np
        import cv2

        luma = np.asarray(frame.convert("L"), dtype=np.float32)
        height, width = luma.shape

        if width == 0 or height == 0:
            return np.zeros((1, 1), dtype=np.float32)

        if width > analysis_width:
            new_height = max(1, int(round(height * analysis_width / width)))
            luma = cv2.resize(luma, (analysis_width, new_height), interpolation=cv2.INTER_AREA)

        return luma

    def _strongest_period(self, series, max_period: int) -> Tuple[Optional[int], float]:
        """Scan lags 2..max_period for the strongest autocorrelation peak of a
        zero-mean series, returning (period, normalized autocorrelation at that
        lag). Returns (None, 0.0) when the series has no variance or no lag
        produces a positive correlation."""
        import numpy as np

        length = len(series)
        if length < 3:
            return None, 0.0

        centred = series - series.mean()
        variance = float((centred * centred).mean())
        if variance == 0.0:
            return None, 0.0

        best_lag, best_corr = 0, 0.0
        for lag in range(2, min(max_period, length) + 1):
            corr = float((centred[:-lag] * centred[lag:]).mean()) / variance
            if corr > best_corr:
                best_lag, best_corr = lag, corr

        if not best_lag:
            return None, 0.0

        return best_lag, max(0.0, best_corr)

def _classify_pulldown(period: Optional[int], ratio: float) -> Optional[str]:
    """Match a measured duplicate period / ratio against known pulldown cadences.
    Returns the label when the period falls into one of the known bands and the
    duplicate ratio is above a minimal plausibility floor, else None (irregular)."""
    if period is None or ratio < 0.05:
        return None
    for label, periods in _PULLDOWN_TABLE:
        if period in periods:
            return label
    return None

@register_video_frame_analyzer_driver(VideoFrameAnalyzerDriverType.OPENCV)
class OpenCvVideoFrameAnalyzerService(VideoFrameAnalyzerDriver):
    def __init__(self, id: str, config: VideoFrameAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "opencv-python", "numpy" ]

    async def _run(
        self,
        action: VideoFrameAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await OpenCvVideoFrameAnalyzerAction(action).run(context)
