from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from collections.abc import AsyncIterator
import asyncio
from mindor.dsl.schema.component import VideoSceneTransitionClassifierComponentConfig, VideoSceneTransitionClassifierDriverType
from mindor.dsl.schema.action import VideoSceneTransitionClassifierActionConfig, NativeVideoSceneTransitionClassifierMode
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
# corner or a hand over the lens also produces flat frames, but the
# endpoint-stability check keeps that from registering as a fade.
_FADE_FLAT_STD = 8.0

# Minimum luma standard deviation at each window endpoint for a boundary
# to be read as a real transition. Rejects clips that are uniformly dim
# throughout — otherwise the whole window reads as a fade through black.
_ENDPOINT_MIN_STD = 12.0

_STREAM_END = object()

class NativeVideoSceneTransitionClassifierAction(VideoSceneTransitionClassifierAction):
    async def _resolve_params(self, mode: NativeVideoSceneTransitionClassifierMode, context: ComponentActionContext) -> Dict[str, Any]:
        if mode == NativeVideoSceneTransitionClassifierMode.CLASSIFY:
            analysis_width           = await context.render_scalar(self.config.analysis_width, int)
            window_size              = await context.render_scalar(self.config.window_size, int)
            cut_mad_threshold        = await context.render_scalar(self.config.cut_mad_threshold, float)
            dissolve_blend_threshold = await context.render_scalar(self.config.dissolve_blend_threshold, float)
            fade_black_threshold     = await context.render_scalar(self.config.fade_black_threshold, float)
            fade_ramp_min_slope      = await context.render_scalar(self.config.fade_ramp_min_slope, float)

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

            if fade_ramp_min_slope <= 0.0:
                raise ValueError(f"'fade_ramp_min_slope' must be positive, got {fade_ramp_min_slope}")

            return {
                "analysis_width":           analysis_width,
                "window_size":              window_size,
                "cut_mad_threshold":        cut_mad_threshold,
                "dissolve_blend_threshold": dissolve_blend_threshold,
                "fade_black_threshold":     fade_black_threshold,
                "fade_ramp_min_slope":      fade_ramp_min_slope,
            }

        raise ValueError(f"Unsupported video scene transition classification mode: {mode}")

    async def _classify(
        self,
        mode: NativeVideoSceneTransitionClassifierMode,
        scenes: ArrayValue,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
        if mode == NativeVideoSceneTransitionClassifierMode.CLASSIFY:
            if streaming:
                return self._stream_scenes(scenes, frames, frame_rate, params, cancellation_token)

            return await self._collect_scenes(scenes, frames, frame_rate, params, cancellation_token)

        raise ValueError(f"Unsupported video scene transition classification mode: {mode}")

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

        * `boundary_windows`:  boundary -> (start_idx, end_idx)  (end exclusive)
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
                            start = max(0, boundary - params["window_size"])
                            end   = boundary + params["window_size"]  # exclusive
                            boundary_windows[boundary] = (start, end)
                            pending_boundaries[boundary] = {}
                            boundary_order.append(boundary)

                            # Reclaim any already-received frames that fall into
                            # this boundary's window.
                            for frame_index in list(recent_frames.keys()):
                                if start <= frame_index < end:
                                    pending_boundaries[boundary][frame_index] = recent_frames.pop(frame_index)

                        previous_scene = item

                        continue

                    if task is frame_next:
                        if item is _STREAM_END:
                            frames_done = True

                            continue

                        frame_index, frame = item
                        max_seen_frame_index = frame_index
                        luma = self._thumb_luma(frame, params["analysis_width"])

                        # Route the new luma into every pending boundary whose
                        # window covers this index. Multiple boundaries can
                        # share a frame when their windows overlap.
                        claimed = False

                        for boundary, (start, end) in boundary_windows.items():
                            if start <= frame_index < end:
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

                    start, end = boundary_windows[boundary]
                    if max_seen_frame_index + 1 >= end or frames_done:
                        thumb_lumas = pending_boundaries.pop(boundary)
                        boundary_windows.pop(boundary)
                        boundary_order.remove(boundary)

                        signals = self._measure_signals(boundary, thumb_lumas, params)
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

    def _thumb_luma(self, frame: "PILImage.Image", analysis_width: int):
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

    def _measure_signals(self, boundary: int, thumb_lumas: Dict[int, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Measure the raw signals used to decide a transition label at a boundary.

        A boundary sits between frames `boundary - 1` and `boundary`. A window of
        size W pulls frames `[boundary - W, boundary + W)` — the first W are the
        "before" side, the last W are the "after" side. `thumb_lumas` maps frame
        index to luma thumbnail; indices outside the available range (video start
        or truncated window at stream end) are simply missing from the dict.

        `min_luma` reports the level a fade passes through: the mean luma of
        the window's flat frames (nearly a single colour) when any exist,
        otherwise the plain window minimum. When flat frames are present, the
        endpoint standard deviations must clear `_ENDPOINT_MIN_STD`; a clip
        that is uniformly dim throughout fails this gate and `min_luma` is
        then reported as the bright window max so the fade branch skips it.
        """
        import numpy as np

        before_window = [ thumb_lumas[index] for index in range(boundary - params["window_size"], boundary) if index in thumb_lumas ]
        after_window  = [ thumb_lumas[index] for index in range(boundary, boundary + params["window_size"]) if index in thumb_lumas ]
        blend_window  = before_window + after_window

        # Pair MAD across the boundary — how different are the two sides' innermost frames.
        if before_window and after_window:
            pair_mad = float(np.abs(before_window[-1] - after_window[0]).mean())
        else:
            pair_mad = 0.0

        # Linear-blend fit — if the in-between frames can be reconstructed as
        # alpha * A + (1-alpha) * B (with monotone alpha), the residual is small.
        blend_residual, blend_length = self._linear_blend_residual(blend_window)

        # Brightness ramp — mean luma over the window, slope per frame.
        window_means = np.asarray([ float(luma.mean()) for luma in blend_window ], dtype=np.float32) if blend_window else np.zeros(0, dtype=np.float32)

        if len(window_means) >= 2:
            indices          = np.arange(len(window_means), dtype=np.float32)
            slope, _offset   = np.polyfit(indices, window_means, 1)
            brightness_slope = float(slope)
            max_luma         = float(window_means.max())
        else:
            brightness_slope = 0.0
            max_luma         = float(window_means[0]) if len(window_means) else 0.0

        # Fade passes through a flat (nearly single-colour) frame. When the
        # window has any such frame, report their mean luma as `min_luma` so
        # the fade branch tests the actual fade level. But only if the two
        # endpoints are real pictures: a uniformly dim clip would otherwise
        # read as a fade along its whole length.
        flat_lumas = [ float(luma.mean()) for luma in blend_window if float(luma.std()) < _FADE_FLAT_STD ]
        endpoints_are_pictures = (
            len(blend_window) > 0
            and float(blend_window[0].std())  > _ENDPOINT_MIN_STD
            and float(blend_window[-1].std()) > _ENDPOINT_MIN_STD
        )

        if flat_lumas and endpoints_are_pictures:
            min_luma = float(np.mean(flat_lumas))
        else:
            min_luma = float(window_means.min()) if len(window_means) else 0.0

        return {
            "pair_mad":          pair_mad,
            "blend_residual":    blend_residual,
            "blend_length":      blend_length,
            "brightness_slope":  brightness_slope,
            "min_luma":          min_luma,
            "max_luma":          max_luma,
        }

    def _linear_blend_residual(self, window_lumas: List[Any]) -> Tuple[float, int]:
        """Fit each middle frame as `first + alpha * (last - first)` with alpha
        unclipped, and return the median scale-normalized residual plus the
        window length. A clean dissolve yields small residuals AND an alpha
        series that rises monotonically across the window — a hard cut
        snaps alpha to 0/1 at the boundary with no progression and fails
        the rising test, so its residual is forced to infinity to keep the
        dissolve branch from accepting it."""
        import numpy as np

        if len(window_lumas) < 3:
            return float("inf"), len(window_lumas)

        first = window_lumas[0]
        last  = window_lumas[-1]
        delta = last - first
        denom = float((delta * delta).sum()) + 1e-6
        scale = float(np.abs(delta).mean()) + 1e-6

        residuals: List[float] = []
        alphas:    List[float] = []

        for index in range(1, len(window_lumas) - 1):
            alpha = float(((window_lumas[index] - first) * delta).sum() / denom)
            alphas.append(alpha)
            residuals.append(float(np.abs(window_lumas[index] - (first + alpha * delta)).mean()) / scale)

        alphas = np.asarray(alphas, dtype=np.float32)
        # The index-correlation + endpoint conditions are from rea-video's
        # `_blend_fit`. The adjacent-diff uniformity gate is additional:
        # upstream rea-video skips `_blend_fit` entirely for hard cuts (its
        # shot detector already labelled them), so a step-shaped alpha
        # `[0,0,...,1,1]` never reaches the test there. Here it does, with
        # correlation ~0.87 against the frame index — just above 0.85. A
        # true dissolve's alpha advances by a near-constant step per frame
        # (max/mean ≈ 1); a step cut concentrates the advance into a
        # single jump (max/mean ≈ N).
        alpha_diffs = np.diff(alphas) if len(alphas) >= 2 else np.zeros(0, dtype=np.float32)
        mean_diff   = float(alpha_diffs.mean()) if len(alpha_diffs) else 0.0
        rising = len(alphas) < 3 or (
            float(np.corrcoef(alphas, np.arange(len(alphas)))[0, 1]) > 0.85
            and alphas[0]  < 0.6
            and alphas[-1] > 0.4
            and mean_diff > 0.0
            and float(alpha_diffs.max()) / mean_diff < 2.0
        )

        return (float(np.median(residuals)) if rising else float("inf")), len(window_lumas)

    def _decide_label(self, signals: Dict[str, Any], params: Dict[str, Any]) -> Tuple[str, float]:
        """Rule chain over the measured signals. Fade and dissolve carry
        multi-signal gates that a hard cut cannot satisfy: a fade requires a
        flat-level `min_luma` AND a ramp slope; a dissolve requires a small
        scale-normalized blend residual AND a monotonically rising alpha. Cut
        is the pair-MAD-spike fallback. Unknown covers boundaries where none
        of the gates fire (often false-positive scene boundaries from frame
        interpolation).
        """
        min_luma         = signals["min_luma"]
        brightness_slope = signals["brightness_slope"]
        blend_residual   = signals["blend_residual"]
        pair_mad         = signals["pair_mad"]

        is_fade_in  = min_luma < params["fade_black_threshold"] and brightness_slope >=  params["fade_ramp_min_slope"]
        is_fade_out = min_luma < params["fade_black_threshold"] and brightness_slope <= -params["fade_ramp_min_slope"]

        if is_fade_in:
            return "fade_in", min(1.0, abs(brightness_slope) / (params["fade_ramp_min_slope"] * 4.0))

        if is_fade_out:
            return "fade_out", min(1.0, abs(brightness_slope) / (params["fade_ramp_min_slope"] * 4.0))

        if blend_residual <= params["dissolve_blend_threshold"] and signals["blend_length"] >= 3:
            return "dissolve", max(0.0, 1.0 - blend_residual / params["dissolve_blend_threshold"])

        if pair_mad >= params["cut_mad_threshold"]:
            return "cut", min(1.0, pair_mad / (params["cut_mad_threshold"] * 2.0))

        return "unknown", 0.0

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
