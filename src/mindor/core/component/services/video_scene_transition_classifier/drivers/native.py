from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
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
    ) -> Dict[str, Any]:
        if mode == NativeVideoSceneTransitionClassifierMode.CLASSIFY:
            return await self._classify_scenes(scenes, frames, frame_rate, params, cancellation_token)

        raise ValueError(f"Unsupported video scene transition classification mode: {mode}")

    async def _classify_scenes(
        self,
        scenes: ArrayValue,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        scenes = await scenes.collect()
        frames = await frames.collect()

        # Boundaries sit between consecutive scenes: the end_frame of scene N
        # is the start of scene N+1. The final scene has no following scene,
        # so its end is the video end, not a transition.
        boundaries: List[int] = [ int(scenes[index]["end_frame"]) for index in range(len(scenes) - 1) ]

        def _classify_scenes() -> Dict[str, Any]:
            import numpy as np

            thumb_lumas = [ self._thumb_luma(frame, params["analysis_width"]) for frame in frames ]

            transitions: List[Dict[str, Any]] = []
            label_counts: Dict[str, int] = { "cut": 0, "dissolve": 0, "fade_in": 0, "fade_out": 0, "wipe": 0, "none": 0 }

            for boundary in boundaries:
                signals = self._measure_signals(boundary, thumb_lumas, params)
                label, confidence = self._decide_label(signals, params)

                transitions.append({
                    "boundary_frame": boundary,
                    "boundary_time":  boundary / frame_rate if frame_rate else None,
                    "label":          label,
                    "confidence":     confidence,
                    "signals":        signals,
                })
                label_counts[label] += 1

            return {
                "transitions":    transitions,
                "cut_count":      label_counts["cut"],
                "dissolve_count": label_counts["dissolve"],
                "fade_in_count":  label_counts["fade_in"],
                "fade_out_count": label_counts["fade_out"],
                "wipe_count":     label_counts["wipe"],
                "none_count":     label_counts["none"],
                "boundary_count": len(boundaries),
                "scene_count":    len(scenes),
                "frame_count":    len(frames),
                "frame_rate":     frame_rate,
                "analysis_width": params["analysis_width"],
                "window_size":    params["window_size"],
            }

        return await self._run_in_executor(_classify_scenes)

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

    def _measure_signals(self, boundary: int, thumb_lumas: List[Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Measure the raw signals used to decide a transition label at a boundary.

        A boundary sits between frames `boundary - 1` and `boundary`. A window of
        size W pulls frames `[boundary - W, boundary + W)` — the first W are the
        "before" side, the last W are the "after" side.
        """
        import numpy as np

        window_size = params["window_size"]
        frame_count = len(thumb_lumas)

        before_start = max(0, boundary - window_size)
        before_end   = boundary
        after_start  = boundary
        after_end    = min(frame_count, boundary + window_size)

        before_window = thumb_lumas[before_start:before_end]
        after_window  = thumb_lumas[after_start:after_end]

        # Pair MAD across the boundary — how different are the two sides' innermost frames.
        if before_window and after_window:
            pair_mad = float(np.abs(before_window[-1] - after_window[0]).mean())
        else:
            pair_mad = 0.0

        # Linear-blend fit — if the in-between frames can be reconstructed as
        # alpha * A + (1-alpha) * B (with monotone alpha), the residual is small.
        blend_window = thumb_lumas[before_start:after_end]
        blend_residual, blend_length = self._linear_blend_residual(blend_window)

        # Brightness ramp — mean luma over the window, slope per frame.
        window_lumas = [ float(luma.mean()) for luma in blend_window ]

        if len(window_lumas) >= 2:
            lumas_array = np.asarray(window_lumas, dtype=np.float32)
            indices     = np.arange(len(lumas_array), dtype=np.float32)
            slope, offset = np.polyfit(indices, lumas_array, 1)
            brightness_slope = float(slope)
            min_luma         = float(lumas_array.min())
            max_luma         = float(lumas_array.max())
        else:
            brightness_slope = 0.0
            min_luma         = float(window_lumas[0]) if window_lumas else 0.0
            max_luma         = float(window_lumas[0]) if window_lumas else 0.0

        return {
            "pair_mad":          pair_mad,
            "blend_residual":    blend_residual,
            "blend_length":      blend_length,
            "brightness_slope":  brightness_slope,
            "min_luma":          min_luma,
            "max_luma":          max_luma,
        }

    def _linear_blend_residual(self, window_lumas: List[Any]) -> Tuple[float, int]:
        """Fit each in-between frame as alpha * first + (1 - alpha) * last and
        return the mean residual. A small residual means the window is a clean
        linear blend (dissolve signature). Returns (residual, blend_length)."""
        import numpy as np

        if len(window_lumas) < 3:
            return float("inf"), len(window_lumas)

        first = window_lumas[0]
        last  = window_lumas[-1]
        delta = last - first
        delta_energy = float((delta * delta).sum())

        if delta_energy == 0.0:
            return float("inf"), len(window_lumas)

        residuals: List[float] = []

        for index in range(1, len(window_lumas) - 1):
            # Per-frame optimal alpha = <frame - last, first - last> / ||first - last||^2
            diff  = window_lumas[index] - last
            alpha = float((diff * delta).sum()) / delta_energy
            alpha = max(0.0, min(1.0, alpha))

            predicted = alpha * first + (1.0 - alpha) * last
            residuals.append(float(np.abs(window_lumas[index] - predicted).mean()))

        return (sum(residuals) / len(residuals)) if residuals else float("inf"), len(window_lumas)

    def _decide_label(self, signals: Dict[str, Any], params: Dict[str, Any]) -> Tuple[str, float]:
        """Rule chain over the measured signals. Order matters — fade is checked
        before dissolve because a fade satisfies the blend-residual test too."""
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

        return "none", 0.0

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
