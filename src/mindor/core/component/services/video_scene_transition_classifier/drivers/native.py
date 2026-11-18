from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from collections.abc import AsyncIterator
import asyncio
from mindor.dsl.schema.component import VideoSceneTransitionClassifierComponentConfig, VideoSceneTransitionClassifierDriverType
from mindor.dsl.schema.action import VideoSceneTransitionClassifierActionConfig
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VideoSceneTransitionClassifierDriver, register_video_scene_transition_classifier_driver
from ..base import ComponentActionContext
from .common import VideoSceneTransitionClassifierAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

# Per-frame luma standard deviation below which a frame reads as "flat"
# (the black/white card a fade passes through). A whip through a dark
# corner or a hand over the lens also produces flat fraㄷmes, but the
# endpoint-stability check keeps that from registering as a fade.
_FADE_FLAT_STD = 8.0

# Minimum luma standard deviation at each window endpoint for a boundary
# to be read as a real transition. Rejects clips that are uniformly dim
# throughout — otherwise the whole window reads as a fade through black.
_ENDPOINT_MIN_STD = 12.0

# Candidate half-widths (in seconds) `_measure_span` tries from smallest to
# largest when narrowing the analysis window to the actual ramp of a gradual
# transition.
_SPAN_SECONDS = (0.1, 0.2, 0.35, 0.6, 1.0, 1.5)

# Maximum MAD between a window endpoint and its outer-pad frames, expressed
# as a share of the window's endpoint-to-endpoint MAD. A half-width whose
# outer pad drifts more than this is inside a wider ramp, not outside it.
_SPAN_PLATEAU = 0.4

_STREAM_END = object()

class NativeVideoSceneTransitionClassifierAction(VideoSceneTransitionClassifierAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        analysis_width             = await context.render_scalar(self.config.analysis_width, int)
        window_size                = await context.render_scalar(self.config.window_size, int)
        cut_mad_threshold          = await context.render_scalar(self.config.cut_mad_threshold, float)
        dissolve_blend_threshold   = await context.render_scalar(self.config.dissolve_blend_threshold, float)
        fade_black_threshold       = await context.render_scalar(self.config.fade_black_threshold, float)
        fade_white_threshold       = await context.render_scalar(self.config.fade_white_threshold, float)
        fade_ramp_min_slope        = await context.render_scalar(self.config.fade_ramp_min_slope, float)
        flash_peak_threshold       = await context.render_scalar(self.config.flash_peak_threshold, float)
        flash_endpoint_gap         = await context.render_scalar(self.config.flash_endpoint_gap, float)
        wipe_edge_threshold        = await context.render_scalar(self.config.wipe_edge_threshold, float)
        wipe_region_pure_threshold = await context.render_scalar(self.config.wipe_region_pure_threshold, float)
        blur_detail_ratio          = await context.render_scalar(self.config.blur_detail_ratio, float)
        jump_block_min_std         = await context.render_scalar(self.config.jump_block_min_std, float)
        jump_block_correlation     = await context.render_scalar(self.config.jump_block_correlation, float)
        jump_min_matching_blocks   = await context.render_scalar(self.config.jump_min_matching_blocks, int)
        jump_min_match_ratio       = await context.render_scalar(self.config.jump_min_match_ratio, float)

        if not 16 <= analysis_width <= 4096:
            raise ValueError(f"'analysis_width' must be between 16 and 4096, got {analysis_width}")

        if not 1 <= window_size <= 64:
            raise ValueError(f"'window_size' must be between 1 and 64, got {window_size}")

        if cut_mad_threshold <= 0.0:
            raise ValueError(f"'cut_mad_threshold' must be positive, got {cut_mad_threshold}")

        if dissolve_blend_threshold <= 0.0:
            raise ValueError(f"'dissolve_blend_threshold' must be positive, got {dissolve_blend_threshold}")

        if fade_black_threshold < 0.0:
            raise ValueError(f"'fade_black_threshold' must be non-negative, got {fade_black_threshold}")

        if fade_white_threshold > 255.0 or fade_white_threshold <= fade_black_threshold:
            raise ValueError(f"'fade_white_threshold' must be greater than 'fade_black_threshold' and at most 255.0, got {fade_white_threshold}")

        if fade_ramp_min_slope <= 0.0:
            raise ValueError(f"'fade_ramp_min_slope' must be positive, got {fade_ramp_min_slope}")

        if flash_peak_threshold <= 0.0 or flash_peak_threshold > 255.0:
            raise ValueError(f"'flash_peak_threshold' must be in (0.0, 255.0], got {flash_peak_threshold}")

        if flash_endpoint_gap < 0.0:
            raise ValueError(f"'flash_endpoint_gap' must be non-negative, got {flash_endpoint_gap}")

        if not 0.0 < wipe_edge_threshold <= 1.0:
            raise ValueError(f"'wipe_edge_threshold' must be in (0.0, 1.0], got {wipe_edge_threshold}")

        if not 0.0 < wipe_region_pure_threshold <= 1.0:
            raise ValueError(f"'wipe_region_pure_threshold' must be in (0.0, 1.0], got {wipe_region_pure_threshold}")

        if not 0.0 < blur_detail_ratio <= 1.0:
            raise ValueError(f"'blur_detail_ratio' must be in (0.0, 1.0], got {blur_detail_ratio}")

        if jump_block_min_std < 0.0:
            raise ValueError(f"'jump_block_min_std' must be non-negative, got {jump_block_min_std}")

        if not 0.0 <= jump_block_correlation <= 1.0:
            raise ValueError(f"'jump_block_correlation' must be between 0.0 and 1.0, got {jump_block_correlation}")

        if not 1 <= jump_min_matching_blocks <= 64:
            raise ValueError(f"'jump_min_matching_blocks' must be between 1 and 64, got {jump_min_matching_blocks}")

        if not 0.0 < jump_min_match_ratio <= 1.0:
            raise ValueError(f"'jump_min_match_ratio' must be in (0.0, 1.0], got {jump_min_match_ratio}")

        return {
            "analysis_width":             analysis_width,
            "window_size":                window_size,
            "cut_mad_threshold":          cut_mad_threshold,
            "dissolve_blend_threshold":   dissolve_blend_threshold,
            "fade_black_threshold":       fade_black_threshold,
            "fade_white_threshold":       fade_white_threshold,
            "fade_ramp_min_slope":        fade_ramp_min_slope,
            "flash_peak_threshold":       flash_peak_threshold,
            "flash_endpoint_gap":         flash_endpoint_gap,
            "wipe_edge_threshold":        wipe_edge_threshold,
            "wipe_region_pure_threshold": wipe_region_pure_threshold,
            "blur_detail_ratio":          blur_detail_ratio,
            "jump_block_min_std":         jump_block_min_std,
            "jump_block_correlation":     jump_block_correlation,
            "jump_min_matching_blocks":   jump_min_matching_blocks,
            "jump_min_match_ratio":       jump_min_match_ratio,
        }

    async def _classify(
        self,
        scenes: ArrayValue,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
        if streaming:
            return self._stream_scenes(scenes, frames, frame_rate, params, cancellation_token)

        return await self._collect_scenes(scenes, frames, frame_rate, params, cancellation_token)

    async def _collect_scenes(
        self,
        scenes: ArrayValue,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        async for scene in self._stream_scenes(scenes, frames, frame_rate, params, cancellation_token):
            results.append(scene)

        return results

    async def _stream_scenes(
        self,
        scenes: ArrayValue,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Concurrently consume `scenes` and `frames` as async streams, emitting
        a transition dict as soon as each boundary's window is complete.

        Two async tasks feed asyncio queues; the main loop awaits whichever
        queue produces first. State kept across iterations:

        * `boundary_windows`:  boundary -> (start_frame, end_frame)  (end exclusive)
        * `pending_boundaries`: boundary -> {frame_idx: luma}
        * `recent_frames`:     frame_idx -> luma  (frames received before any
                                                   boundary claimed them; held
                                                   in case a later scene does)

        Memory stays bounded by the number of in-flight windows: once a boundary
        is complete it is emitted and dropped. `recent_frames` is pruned whenever
        we learn no future scene can land in a given index range.
        """
        scene_queue: asyncio.Queue = asyncio.Queue()
        frame_queue: asyncio.Queue = asyncio.Queue()

        async def _consume_scenes() -> None:
            try:
                async for scene in scenes:
                    await scene_queue.put(scene)
            finally:
                await scene_queue.put(_STREAM_END)

        async def _consume_frames() -> None:
            try:
                index = 0
                async for frame in frames:
                    await frame_queue.put((index, frame))
                    index += 1
            finally:
                await frame_queue.put(_STREAM_END)

        scene_task = asyncio.create_task(_consume_scenes())
        frame_task = asyncio.create_task(_consume_frames())

        pending_boundaries: Dict[int, Dict[int, Any]] = {}
        boundary_windows:   Dict[int, Tuple[int, int]] = {}
        recent_frames:      Dict[int, Any] = {}
        boundary_order:     List[int] = []  # emission order (scene arrival order)

        previous_scene: Optional[Dict[str, Any]] = None
        scenes_done = False
        frames_done = False
        max_seen_frame_index = -1

        try:
            while not (scenes_done and frames_done):
                scene_next = asyncio.create_task(scene_queue.get()) if not scenes_done else None
                frame_next = asyncio.create_task(frame_queue.get()) if not frames_done else None

                pending_tasks = [ task for task in (scene_next, frame_next) if task is not None ]
                done, _ = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)

                # Keep whichever task wasn't ready — it will be the first wait on
                # the next loop iteration via a fresh get() wrap (we cancel the
                # unused one to avoid leaking a pending Queue.get).
                for task in pending_tasks:
                    if task not in done:
                        task.cancel()

                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass

                for task in done:
                    item = task.result()

                    if task is scene_next:
                        if item is _STREAM_END:
                            scenes_done = True

                            continue

                        # The boundary is the current scene's end_frame — but
                        # only when there is a following scene. We learn that
                        # there IS a following scene only when the NEXT one
                        # arrives, so we promote the previous scene's end_frame
                        # into a boundary here.
                        if previous_scene is not None:
                            boundary = int(previous_scene["end_frame"])
                            start_frame = max(0, boundary - params["window_size"])
                            end_frame   = boundary + params["window_size"]  # exclusive
                            boundary_windows[boundary] = (start_frame, end_frame)
                            pending_boundaries[boundary] = {}
                            boundary_order.append(boundary)

                            # Reclaim any already-received frames that fall into
                            # this boundary's window.
                            for frame_index in list(recent_frames.keys()):
                                if start_frame <= frame_index < end_frame:
                                    pending_boundaries[boundary][frame_index] = recent_frames.pop(frame_index)

                        previous_scene = item

                        continue

                    if task is frame_next:
                        if item is _STREAM_END:
                            frames_done = True

                            continue

                        frame_index, frame = item
                        max_seen_frame_index = frame_index
                        luma = self._luma_thumbnail(frame, params["analysis_width"])

                        # Route the new luma into every pending boundary whose
                        # window covers this index. Multiple boundaries can
                        # share a frame when their windows overlap.
                        claimed = False

                        for boundary, (start_frame, end_frame) in boundary_windows.items():
                            if start_frame <= frame_index < end_frame:
                                pending_boundaries[boundary][frame_index] = luma
                                claimed = True

                        if not claimed:
                            # Hold it for future scenes — but drop frames that
                            # can no longer land in any window: once scenes are
                            # done, nothing further can claim them.
                            if not scenes_done:
                                recent_frames[frame_index] = luma

                # Emit transitions for any boundary whose window is fully
                # covered (either its end index is past max_seen_frame_index,
                # or the frame stream ended).
                for boundary in list(boundary_order):
                    if boundary not in boundary_windows:
                        continue

                    _, end_frame = boundary_windows[boundary]

                    if max_seen_frame_index + 1 >= end_frame or frames_done:
                        thumb_lumas = pending_boundaries.pop(boundary)
                        boundary_windows.pop(boundary)
                        boundary_order.remove(boundary)

                        signals = self._measure_signals(boundary, thumb_lumas, frame_rate, params)
                        label, confidence = self._decide_label(signals, params)

                        yield {
                            "boundary_frame": boundary,
                            "boundary_time":  boundary / frame_rate if frame_rate else None,
                            "label":          label,
                            "confidence":     confidence,
                            "signals":        signals,
                        }

            # Scenes done: the previous_scene's end_frame is the end of video
            # (no following scene), so it is NOT a boundary. Nothing to flush
            # from previous_scene.
        finally:
            scene_task.cancel()
            frame_task.cancel()

            for task in (scene_task, frame_task):
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    def _measure_signals(
        self,
        boundary: int,
        thumb_lumas: Dict[int, Any],
        frame_rate: Optional[float],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Measure the raw signals used to decide a transition label at a boundary.

        A boundary sits between frames `boundary - 1` and `boundary`. `window_size`
        bounds how far we look on each side; the actual analysis window is then
        narrowed by `_measure_span` to the smallest half-width whose outer pad
        holds steady and whose inner progress curve covers the full ramp. When
        no narrower span satisfies the gates — or when `frame_rate` is unknown —
        the full `[boundary - W, boundary + W)` bound is used. `thumb_lumas`
        maps frame index to luma thumbnail; indices outside the available range
        (video start or truncated window at stream end) are simply missing from
        the dict.

        `min_luma` reports the level a fade passes through: the mean luma of
        the window's flat frames (nearly a single colour) when any exist,
        otherwise the plain window minimum. When flat frames are present, the
        endpoint standard deviations must clear `_ENDPOINT_MIN_STD`; a clip
        that is uniformly dim throughout fails this gate and `min_luma` is
        then reported as the bright window max so the fade branch skips it.
        """
        import numpy as np

        half_width    = self._measure_span(boundary, thumb_lumas, frame_rate, params)
        before_window = [ thumb_lumas[index] for index in range(boundary - half_width, boundary) if index in thumb_lumas ]
        after_window  = [ thumb_lumas[index] for index in range(boundary, boundary + half_width) if index in thumb_lumas ]
        blend_window  = before_window + after_window

        # Pair MAD across the boundary — how different are the two sides' innermost frames.
        if before_window and after_window:
            pair_mad = float(np.abs(before_window[-1] - after_window[0]).mean())
        else:
            pair_mad = 0.0

        # Same-structure (jump vs cut): block-wise brightness-normalized
        # correlation across the boundary pair. A real cut shows unrelated
        # pictures so most blocks fail to line up; a jump (same shot, only
        # lighting / exposure changed) keeps the picture detail intact and
        # most blocks correlate once brightness is removed.
        if before_window and after_window:
            has_same_structure = self._same_structure(before_window[-1], after_window[0], params)
        else:
            has_same_structure = False

        # Linear-blend fit — if the in-between frames can be reconstructed as
        # alpha * A + (1-alpha) * B (with monotone alpha), the residual is small.
        blend_residual, blend_length = self._linear_blend_residual(blend_window)

        # Brightness ramp — mean luma over the window, slope per frame.
        window_means = np.asarray([ float(luma.mean()) for luma in blend_window ], dtype=np.float32) if blend_window else np.zeros(0, dtype=np.float32)

        if len(window_means) >= 2:
            indices          = np.arange(len(window_means), dtype=np.float32)
            slope, _         = np.polyfit(indices, window_means, 1)
            brightness_slope = float(slope)
        else:
            brightness_slope = 0.0

        # Fade passes through a flat (nearly single-colour) frame. When the
        # window has any such frame AND the two endpoints are real pictures,
        # report `min_luma` / `max_luma` as the mean luma of the flat frames
        # so the fade branch can test fade-through-black (small min_luma) or
        # fade-through-white (large max_luma). Without the endpoint guard a
        # uniformly dim clip would read as a fade along its whole length;
        # without the flat-frame check a dissolve that crosses mid-grey
        # would also look like a fade.
        flat_lumas = [ float(luma.mean()) for luma in blend_window if float(luma.std()) < _FADE_FLAT_STD ]

        endpoints_are_pictures = (
            len(blend_window) > 0
            and (
                float(blend_window[0].std()) > _ENDPOINT_MIN_STD
                and float(blend_window[-1].std()) > _ENDPOINT_MIN_STD
            )
        )

        # Looser gate than `endpoints_are_pictures` — only one endpoint has
        # to be a real picture. Fade_in / fade_out keep one shot and one
        # flat colour by definition, so a two-sided picture requirement
        # would reject them; this one-sided gate still rejects all-flat
        # clips (a bright burst between two grey shots would otherwise
        # flip the fade-through-white branch).
        has_picture_endpoint = (
            len(blend_window) > 0
            and (
                float(blend_window[0].std()) > _ENDPOINT_MIN_STD
                or float(blend_window[-1].std()) > _ENDPOINT_MIN_STD
            )
        )

        if flat_lumas and endpoints_are_pictures:
            flat_level = float(np.mean(flat_lumas))
            min_luma = flat_level
            max_luma = flat_level
        else:
            min_luma = float(window_means.min()) if len(window_means) else 0.0
            max_luma = float(window_means.max()) if len(window_means) else 0.0

        # Peak luma — raw window maximum, unaffected by the flat-frame
        # reinterpretation above. Flash detection needs the real bright burst
        # even when the burst does not cross the flat-frame std threshold.
        peak_luma = float(window_means.max()) if len(window_means) else 0.0

        # Endpoint max luma — the brighter of the two window endpoints, used
        # as the reference level a flash must stand out from.
        endpoint_max_luma = float(max(window_means[0], window_means[-1])) if len(window_means) else 0.0

        # Straight-edge fit (wipe / slide): can each in-between frame be
        # explained as the old picture on one side of a moving straight
        # edge and the new picture on the other? Returns the relative
        # residual plus the best mode + direction.
        if len(blend_window) >= 3:
            edge_fit = self._edge_fit(blend_window[0], blend_window[-1], blend_window[1:-1])
        else:
            edge_fit = None

        # Region fit (iris / non-straight wipe): block-by-block each
        # in-between frame is either the old picture or the new one, and
        # the "new" region grows across the window.
        if len(blend_window) >= 3:
            region_fit = self._region_fit(blend_window[0], blend_window[-1], blend_window[1:-1])
        else:
            region_fit = None

        # Blur ratio (defocus / motion-smear): compare the minimum
        # per-axis gradient of the in-between frames to the median gradient
        # of the two endpoints. A defocus transition drops detail (small
        # grad) in both axes while the endpoints remain sharp — the
        # resulting ratios `rx`, `ry` fall well below 1.0. The endpoints
        # must themselves be sharp pictures (same std gate used for fade
        # endpoints); a flat-grey clip has no detail to lose and must not
        # read as blur.
        if len(blend_window) >= 3 and endpoints_are_pictures:
            endpoint_gradients  = [ self._frame_gradient(blend_window[0]), self._frame_gradient(blend_window[-1]) ]
            horizontal_endpoint = float(np.median([ gradient[0] for gradient in endpoint_gradients ])) + 1e-6
            vertical_endpoint   = float(np.median([ gradient[1] for gradient in endpoint_gradients ])) + 1e-6
            inside_gradients    = [ self._frame_gradient(frame) for frame in blend_window[1:-1] ]
            blur_rx             = min(gradient[0] for gradient in inside_gradients) / horizontal_endpoint
            blur_ry             = min(gradient[1] for gradient in inside_gradients) / vertical_endpoint
        else:
            blur_rx = 1.0
            blur_ry = 1.0

        return {
            "pair_mad":               pair_mad,
            "has_same_structure":     has_same_structure,
            "blend_residual":         blend_residual,
            "blend_length":           blend_length,
            "brightness_slope":       brightness_slope,
            "min_luma":               min_luma,
            "max_luma":               max_luma,
            "peak_luma":              peak_luma,
            "endpoint_max_luma":      endpoint_max_luma,
            "endpoints_are_pictures": endpoints_are_pictures,
            "has_picture_endpoint":   has_picture_endpoint,
            "edge_residual":          edge_fit["residual"] if edge_fit else float("inf"),
            "edge_mode":              edge_fit["mode"] if edge_fit else None,
            "edge_direction":         edge_fit["direction"] if edge_fit else None,
            "region_pure":            region_fit["pure"] if region_fit else 0.0,
            "region_direction":       region_fit["direction"] if region_fit else None,
            "blur_rx":                blur_rx,
            "blur_ry":                blur_ry,
        }

    def _measure_span(
        self,
        boundary: int,
        thumb_lumas: Dict[int, Any],
        frame_rate: Optional[float],
        params: Dict[str, Any]
    ) -> int:
        """Find the smallest half-width whose outer pad holds steady and whose
        inner progress curve covers the full ramp of a gradual transition.
        Falls back to the full `window_size` bound when no narrower half-width
        qualifies, when `frame_rate` is unknown (pad has no second-based
        scale), or when the needed frames fall outside `thumb_lumas`."""
        import numpy as np

        window_size = params["window_size"]

        if frame_rate is None:
            return window_size

        for half_width in sorted({ max(2, int(round(seconds * frame_rate))) for seconds in _SPAN_SECONDS }):
            pad = max(2, min(half_width, int(round(0.2 * frame_rate))))

            # Outer pad must fit inside the streaming buffer `window_size`:
            # the buffer holds `[boundary - W, boundary + W)` so `half_width
            # + pad <= W` is the exact reach we can inspect.
            if half_width + pad > window_size:
                break

            before_frame = thumb_lumas.get(boundary - half_width)
            after_frame  = thumb_lumas.get(boundary + half_width - 1)
            outer_before = [ thumb_lumas.get(index) for index in range(boundary - half_width - pad, boundary - half_width) ]
            outer_after  = [ thumb_lumas.get(index) for index in range(boundary + half_width, boundary + half_width + pad) ]

            if before_frame is None or after_frame is None or any(frame is None for frame in outer_before + outer_after):
                continue

            before_after_diff = float(np.abs(before_frame - after_frame).mean()) + 1e-6

            # Outer pad must stay close to the window endpoint: a wider ramp
            # that keeps changing beyond this half-width fails the plateau
            # gate and we try the next larger half-width.
            if max(float(np.abs(frame - before_frame).mean()) for frame in outer_before) > _SPAN_PLATEAU * before_after_diff:
                continue

            if max(float(np.abs(frame - after_frame).mean()) for frame in outer_after) > _SPAN_PLATEAU * before_after_diff:
                continue

            # Inner progress curve must reach both ends: starts below 0.12,
            # ends above 0.88. Otherwise the ramp is wider than this window.
            inner_progress = []
            inner_complete = True

            for index in range(boundary - half_width, boundary + half_width):
                middle_frame = thumb_lumas.get(index)

                if middle_frame is None:
                    inner_complete = False

                    break

                before_diff = float(np.abs(middle_frame - before_frame).mean())
                after_diff  = float(np.abs(middle_frame - after_frame).mean())
                inner_progress.append(before_diff / (before_diff + after_diff + 1e-6))

            if not inner_complete:
                continue

            if inner_progress[0] > 0.12 or inner_progress[-1] < 0.88:
                continue

            return half_width

        return window_size

    def _same_structure(self, before: Any, after: Any, params: Dict[str, Any]) -> bool:
        """Block-wise brightness-normalized correlation check — True when
        the two frames show the same scene under different light (lamp
        switched on, exposure ramp, colour flash). Separates a jump (same
        shot, lighting change) from a cut (different shot). Flat blocks
        have no detail to line up and are skipped; the boundary is treated
        as same-structure only when enough detailed blocks match."""
        height, width = before.shape
        block_height  = max(4, height // 8)
        block_width   = max(4, width  // 6)
        min_std       = params["jump_block_min_std"]
        min_corr      = params["jump_block_correlation"]

        matching = 0
        detailed = 0

        for y in range(0, height - block_height + 1, block_height):
            for x in range(0, width - block_width + 1, block_width):
                before_block = before[y:y + block_height, x:x + block_width]
                after_block  = after[y:y + block_height, x:x + block_width]
                before_std   = float(before_block.std())
                after_std    = float(after_block.std())

                if before_std < min_std or after_std < min_std:
                    continue  # flat block: no detail to line up

                before_centered = before_block - before_block.mean()
                after_centered  = after_block  - after_block.mean()
                correlation     = float((before_centered * after_centered).mean() / (before_std * after_std))

                detailed += 1

                if correlation > min_corr:
                    matching += 1

        if detailed < params["jump_min_matching_blocks"]:
            return False

        return matching / detailed > params["jump_min_match_ratio"]

    def _linear_blend_residual(self, window_lumas: List[Any]) -> Tuple[float, int]:
        """Fit each middle frame as `first_frame + alpha * (last_frame -
        first_frame)` with alpha unclipped, and return the median scale-
        normalized residual plus the window length. A clean dissolve
        yields small residuals AND an alpha series that rises monotonically
        across the window — a hard cut snaps alpha to 0/1 at the boundary
        with no progression and fails the rising test, so its residual is
        forced to infinity to keep the dissolve branch from accepting it."""
        import numpy as np

        if len(window_lumas) < 3:
            return float("inf"), len(window_lumas)

        first_frame = window_lumas[0]
        last_frame  = window_lumas[-1]
        delta = last_frame - first_frame
        denom = float((delta * delta).sum()) + 1e-6
        scale = float(np.abs(delta).mean()) + 1e-6

        residuals: List[float] = []
        alphas:    List[float] = []

        for index in range(1, len(window_lumas) - 1):
            alpha = float(((window_lumas[index] - first_frame) * delta).sum() / denom)
            alphas.append(alpha)
            residuals.append(float(np.abs(window_lumas[index] - (first_frame + alpha * delta)).mean()) / scale)

        alphas = np.asarray(alphas, dtype=np.float32)
        # The index-correlation + endpoint conditions check that alpha
        # grows monotonically from 0 to 1 across the window. The adjacent-
        # diff uniformity gate is extra: a step-shaped alpha `[0,0,...,1,1]`
        # (a hard cut with no upstream filter) still correlates ~0.87 with
        # the frame index — just above 0.85. A true dissolve's alpha
        # advances by a near-constant step per frame (max/mean ≈ 1); a
        # step cut concentrates the advance into a single jump (max/mean
        # ≈ N).
        alpha_diffs = np.diff(alphas) if len(alphas) >= 2 else np.zeros(0, dtype=np.float32)
        mean_diff   = float(alpha_diffs.mean()) if len(alpha_diffs) else 0.0

        rising = len(alphas) < 3 or (
            float(np.corrcoef(alphas, np.arange(len(alphas)))[0, 1]) > 0.85
            and alphas[0]  < 0.6
            and alphas[-1] > 0.4
            and mean_diff > 0.0
            and float(alpha_diffs.max()) / mean_diff < 2.0
        )

        residual = float(np.median(residuals)) if rising else float("inf")

        return residual, len(window_lumas)

    def _frame_gradient(self, frame: Any) -> Tuple[float, float]:
        """Mean absolute per-axis gradient of a luma thumbnail. The pair
        (horizontal, vertical) measures horizontal and vertical detail; a
        sharp picture has both >> 0, a defocused frame or a flat colour has
        both ~ 0."""
        import numpy as np

        horizontal = float(np.abs(np.diff(frame, axis=1)).mean())
        vertical   = float(np.abs(np.diff(frame, axis=0)).mean())

        return horizontal, vertical

    def _edge_fit(self, before: Any, after: Any, middle_frames: List[Any]) -> Optional[Dict[str, Any]]:
        """Best straight-edge explanation of the in-between frames.

        For each (direction, mode) pair, synthesize the frame that would
        appear once the edge has travelled `distance` pixels, compare against
        each middle frame, keep the best match. A good fit requires the median
        residual to be below 0.38 of the raw before/after difference AND the
        edge position to travel monotonically across the span. Modes: `wipe`
        (nothing moves), `push` / `cover` / `reveal` (one or both pictures
        slide). Direction: `left` / `right` / `up` / `down`.
        """
        import numpy as np

        if not middle_frames:
            return None

        before_after_diff = float(np.abs(before - after).mean()) + 1e-6
        best: Optional[Dict[str, Any]] = None

        for direction in ("left", "right", "up", "down"):
            size  = before.shape[1] if direction in ("left", "right") else before.shape[0]
            steps = np.unique(np.linspace(0, size, num=min(size + 1, 33)).astype(int))

            for mode in ("wipe", "push", "cover", "reveal"):
                candidates = [ self._compose_moving_edge(before, after, mode, direction, int(step)) for step in steps ]
                residuals, positions = [], []

                for middle_frame in middle_frames:
                    errors    = [ float(np.abs(middle_frame - candidate).mean()) for candidate in candidates ]
                    best_step = int(np.argmin(errors))
                    residuals.append(errors[best_step] / before_after_diff)
                    positions.append(steps[best_step] / size)

                residual = float(np.median(residuals))

                # Nothing moving is the simpler reading; a moving mode has to
                # fit clearly better to be chosen over wipe.
                if best is None or residual < best["residual"] * (0.8 if best["mode"] == "wipe" and mode != "wipe" else 1.0):
                    best = { "mode": mode, "direction": direction, "residual": residual, "positions": positions }

        if best is None or best["residual"] > 0.38:
            return None

        positions = np.asarray(best["positions"], dtype=np.float32)

        if len(positions) >= 3 and (
            float(np.corrcoef(positions, np.arange(len(positions)))[0, 1]) < 0.8
            or positions[-1] - positions[0] < 0.3
        ):
            return None  # the edge has to travel across the frame

        return { "mode": best["mode"], "direction": best["direction"], "residual": best["residual"] }

    def _compose_moving_edge(self, before: Any, after: Any, mode: str, direction: str, distance: int) -> Any:
        """Frame a straight-edge transition shows once the edge has travelled
        `distance` pixels in `direction`. `mode`: `wipe` (nothing moves),
        `push` (both pictures move), `cover` (new slides in over old),
        `reveal` (old slides away off new)."""
        import numpy as np

        if direction in ("up", "down"):
            return self._compose_moving_edge(before.T, after.T, mode, "left" if direction == "up" else "right", distance).T

        if direction == "right":
            return self._compose_moving_edge(before[:, ::-1], after[:, ::-1], mode, "left", distance)[:, ::-1]

        width = before.shape[1]

        if distance <= 0:
            return before.copy()

        if distance >= width:
            return after.copy()

        frame = np.empty_like(before)
        frame[:, :width - distance] = before[:, distance:] if mode in ("push", "reveal") else before[:, :width - distance]
        frame[:, width - distance:] = after[:, :distance]  if mode in ("push", "cover")  else after[:, width - distance:]

        return frame

    def _region_fit(self, before: Any, after: Any, middle_frames: List[Any]) -> Optional[Dict[str, Any]]:
        """Wipe of any shape: block by block every in-between frame is the
        old picture or the new one, and the new region grows. Direction
        from the order in which the blocks turn: `left`/`right`/`up`/`down`
        for a straight edge, `center_out`/`edges_in` for an iris,
        `diagonal` for a corner wipe."""
        import numpy as np

        if len(middle_frames) < 2:
            return None

        before_after_diff = self._block_diff(before, after)
        significant = before_after_diff > max(10.0, 0.5 * float(np.median(before_after_diff)))

        if significant.mean() < 0.4:
            return None

        pure_shares: List[float] = []
        new_masks:   List[Any]   = []

        for middle_frame in middle_frames:
            middle_before_diff = self._block_diff(middle_frame, before)
            middle_after_diff  = self._block_diff(middle_frame, after)
            pure_shares.append(float((np.minimum(middle_before_diff, middle_after_diff)[significant] < 0.4 * before_after_diff[significant]).mean()))
            new_masks.append(middle_after_diff < middle_before_diff)

        new_shares = [ float(mask[significant].mean()) for mask in new_masks ]

        # Judge pure-ness only where the two pictures share the frame; half-
        # way through a dissolve no block is purely old or purely new even
        # when the endpoints look clean.
        central_pure_shares = [ pure for pure, new in zip(pure_shares, new_shares) if 0.2 < new < 0.8 ] or pure_shares

        if min(central_pure_shares) < 0.6:
            return None

        if float(np.percentile(pure_shares, 20)) < 0.7:
            return None

        if new_shares[-1] - new_shares[0] < 0.3:
            return None

        # Blocks that turn and then turn back are motion, not a wipe.
        flips = np.diff(np.asarray(new_masks, dtype=np.int8), axis=0)

        if float((flips < 0).any(axis=0)[significant].mean()) > 0.2:
            return None

        # First in-between frame showing the new picture, per block.
        turn_time = np.asarray(new_masks, dtype=np.float32).argmax(axis=0).astype(np.float32)
        turn_time[~np.asarray(new_masks).any(axis=0)] = len(middle_frames)

        grid_height, grid_width = turn_time.shape
        y_axis, x_axis = np.mgrid[0:grid_height, 0:grid_width].astype(np.float32)
        radius_axis = np.hypot((x_axis - (grid_width - 1) / 2) / grid_width, (y_axis - (grid_height - 1) / 2) / grid_height)

        def _axis_correlation(axis: Any) -> float:
            times = turn_time[significant]
            coord = axis[significant]

            return float(np.corrcoef(times, coord)[0, 1]) if times.std() > 0 and coord.std() > 0 else 0.0

        corr_x      = _axis_correlation(x_axis)
        corr_y      = _axis_correlation(y_axis)
        corr_radius = _axis_correlation(radius_axis)

        direction = None

        if max(abs(corr_x), abs(corr_y), abs(corr_radius)) >= 0.55:
            if abs(corr_radius) >= max(abs(corr_x), abs(corr_y)):
                direction = "center_out" if corr_radius > 0 else "edges_in"
            elif min(abs(corr_x), abs(corr_y)) >= 0.45:
                direction = "diagonal"
            elif abs(corr_x) > abs(corr_y):
                direction = "right" if corr_x > 0 else "left"
            else:
                direction = "down" if corr_y > 0 else "up"

        return { "direction": direction, "pure": float(np.median(pure_shares)) }

    def _block_diff(self, before: Any, after: Any, shift: int = 2) -> Any:
        """Per-block mean `|before - after|` on a 6x8 grid, taking the best of
        a few small shifts so that ordinary subject motion inside the shot
        does not read as a different picture."""
        import numpy as np

        height, width = before.shape
        best: Optional[Any] = None

        for shift_y, shift_x in ((0, 0), (shift, 0), (-shift, 0), (0, shift), (0, -shift)):
            shifted = np.roll(after, (shift_y, shift_x), axis=(0, 1))
            diff    = np.abs(before - shifted)[shift:height - shift, shift:width - shift]
            pooled  = self._mean_pool(diff, (6, 8))
            best    = pooled if best is None else np.minimum(best, pooled)

        return best

    def _mean_pool(self, array: Any, grid: Tuple[int, int]) -> Any:
        """Downsample `array` to the given (rows, cols) grid by averaging
        each block. numpy replacement for `cv2.resize(..., INTER_AREA)`
        on integer-divisible shapes; for other shapes the array is cropped
        to the nearest multiple of the grid."""
        grid_rows, grid_cols = grid
        height, width = array.shape
        block_height  = max(1, height // grid_rows)
        block_width   = max(1, width  // grid_cols)

        array = array[: grid_rows * block_height, : grid_cols * block_width]

        return array.reshape(grid_rows, block_height, grid_cols, block_width).mean(axis=(1, 3))

    def _decide_label(self, signals: Dict[str, Any], params: Dict[str, Any]) -> Tuple[str, float]:
        """Rule chain over the measured signals: fade and flash gate first
        (both require specific luma shapes a cut cannot forge), then a cut
        fast-path intercepts constant-colour cuts that would otherwise fool
        `_edge_fit` into a perfect straight-edge fit. Wipe/slide, blur,
        dissolve, and the pair-MAD fallback follow. Each cut gate consults
        `has_same_structure` to redirect same-shot lighting changes to the
        `jump` label instead of `cut`. Unknown covers boundaries where none
        of the gates fire (often false-positive scene boundaries from frame
        interpolation).
        Fade uses a one-sided picture gate (`has_picture_endpoint`) so
        fade_in / fade_out carrying exactly one shot and one flat colour
        still fire (a two-sided picture requirement would reject them).
        """
        min_luma             = signals["min_luma"]
        max_luma             = signals["max_luma"]
        brightness_slope     = signals["brightness_slope"]
        blend_residual       = signals["blend_residual"]
        pair_mad             = signals["pair_mad"]
        has_picture_endpoint = signals["has_picture_endpoint"]
        has_same_structure   = signals["has_same_structure"]

        # A fade passes through a flat (nearly single-colour) frame; `min_luma`
        # (reinterpreted in _measure_signals) and `max_luma` identify whether
        # that flat frame is near-black or near-white. The slope direction
        # alone does not tell fade-in from fade-out — black and white fades
        # reverse its meaning (`black → picture` and `white → picture` are
        # both fade-ins, with opposite slope signs). We orient by whether
        # the slope points away from the flat colour (fade-in: picture
        # emerging from the flat frame) or towards it (fade-out). The
        # one-sided picture gate rejects all-flat clips so a bright burst
        # between two grey shots cannot flip the fade-through-white branch.
        if has_picture_endpoint and min_luma < params["fade_black_threshold"]:
            if brightness_slope >=  params["fade_ramp_min_slope"]:
                return "fade_in",  min(1.0, abs(brightness_slope) / (params["fade_ramp_min_slope"] * 4.0))

            if brightness_slope <= -params["fade_ramp_min_slope"]:
                return "fade_out", min(1.0, abs(brightness_slope) / (params["fade_ramp_min_slope"] * 4.0))

        if has_picture_endpoint and max_luma > params["fade_white_threshold"]:
            if brightness_slope <= -params["fade_ramp_min_slope"]:
                return "fade_in",  min(1.0, abs(brightness_slope) / (params["fade_ramp_min_slope"] * 4.0))

            if brightness_slope >=  params["fade_ramp_min_slope"]:
                return "fade_out", min(1.0, abs(brightness_slope) / (params["fade_ramp_min_slope"] * 4.0))

        # Flash: a bright burst (e.g. light leak, camera flash) between two
        # normal shots. The window peak clears an absolute threshold AND
        # stands out from the brighter endpoint by a fixed gap.
        peak_luma         = signals["peak_luma"]
        endpoint_max_luma = signals["endpoint_max_luma"]

        if peak_luma >= params["flash_peak_threshold"] and peak_luma >= endpoint_max_luma + params["flash_endpoint_gap"]:
            return "flash", min(1.0, (peak_luma - endpoint_max_luma) / (params["flash_endpoint_gap"] * 2.0))

        edge_residual    = signals["edge_residual"]
        edge_mode        = signals["edge_mode"]
        region_pure      = signals["region_pure"]
        region_direction = signals["region_direction"]

        # Cut fast-path: a constant-colour cut whose `_edge_fit` fits
        # trivially would be swept into the wipe/slide branches without
        # this guard. Fire it when the pair-MAD spike is accompanied by
        # the absence of a rising blend (step-shaped alpha fails the
        # uniformity gate, leaving `blend_residual == inf`). A jump
        # (same shot, lighting change only) also shows a pair-MAD spike
        # with no rising blend; `has_same_structure` separates the two.
        if pair_mad >= params["cut_mad_threshold"] and blend_residual == float("inf"):
            if has_same_structure:
                return "jump", min(1.0, pair_mad / (params["cut_mad_threshold"] * 2.0))

            return "cut", min(1.0, pair_mad / (params["cut_mad_threshold"] * 2.0))

        # Wipe (iris) first: a block-wise region fit whose direction is
        # center_out / edges_in wins over a straight edge unless the edge
        # fit is near-perfect.
        is_iris_wipe = region_direction in ("center_out", "edges_in")

        if is_iris_wipe and region_pure >= params["wipe_region_pure_threshold"] and not (edge_mode is not None and edge_residual < 0.1):
            return "wipe", min(1.0, region_pure)

        # Straight-edge wipe/slide: residual must clear the edge threshold
        # AND be clearly better than the dissolve fit (prevents a dissolve
        # with modest translation from reading as a slide).
        if edge_mode is not None and edge_residual <= params["wipe_edge_threshold"] and edge_residual < 0.6 * blend_residual:
            label = "wipe" if edge_mode == "wipe" else "slide"

            return label, max(0.0, 1.0 - edge_residual / params["wipe_edge_threshold"])

        # Region fit with any direction: block-wise wipe that is not a
        # straight edge (e.g. shape-mask wipe).
        if region_direction is not None and region_pure >= params["wipe_region_pure_threshold"]:
            return "wipe", min(1.0, region_pure)

        # Blur (defocus): detail drops in both axes across the window
        # relative to the endpoints. The rising-blend gate for dissolve
        # also fires on a defocus-and-back (luma ramps smoothly), so blur
        # must run before dissolve or a soft blur reads as a dissolve.
        blur_rx = signals["blur_rx"]
        blur_ry = signals["blur_ry"]

        if max(blur_rx, blur_ry) < params["blur_detail_ratio"]:
            return "blur", min(1.0, 1.0 - max(blur_rx, blur_ry) / params["blur_detail_ratio"])

        if blend_residual <= params["dissolve_blend_threshold"] and signals["blend_length"] >= 3:
            return "dissolve", max(0.0, 1.0 - blend_residual / params["dissolve_blend_threshold"])

        if pair_mad >= params["cut_mad_threshold"]:
            if has_same_structure:
                return "jump", min(1.0, pair_mad / (params["cut_mad_threshold"] * 2.0))

            return "cut", min(1.0, pair_mad / (params["cut_mad_threshold"] * 2.0))

        return "unknown", 0.0

    def _luma_thumbnail(self, frame: "PILImage.Image", analysis_width: int):
        """Resample a frame to `analysis_width` on the long axis and return BT.601 luma as float32."""
        import numpy as np

        width, height = frame.size

        if width == 0 or height == 0:
            return np.zeros((1, 1), dtype=np.float32)

        if width > analysis_width:
            scale = analysis_width / width
            new_size = (analysis_width, max(1, int(round(height * scale))))
            frame = frame.resize(new_size)

        return np.asarray(frame.convert("L"), dtype=np.float32)

@register_video_scene_transition_classifier_driver(VideoSceneTransitionClassifierDriverType.NATIVE)
class NativeVideoSceneTransitionClassifierService(VideoSceneTransitionClassifierDriver):
    def __init__(self, id: str, config: VideoSceneTransitionClassifierComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "numpy" ]

    async def _run(
        self,
        action: VideoSceneTransitionClassifierActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeVideoSceneTransitionClassifierAction(action).run(context)
