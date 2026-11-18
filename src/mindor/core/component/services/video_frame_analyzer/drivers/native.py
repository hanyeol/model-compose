from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Dict, Any, Union, Tuple
from mindor.dsl.schema.component import VideoFrameAnalyzerComponentConfig, VideoFrameAnalyzerDriverType
from mindor.dsl.schema.action import VideoFrameAnalyzerActionConfig, NativeVideoFrameAnalyzerMetric
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VideoFrameAnalyzerDriver, register_video_frame_analyzer_driver
from ..base import ComponentActionContext
from .common import VideoFrameAnalyzerAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

class NativeVideoFrameAnalyzerAction(VideoFrameAnalyzerAction):
    async def _resolve_params(self, metric: NativeVideoFrameAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        if metric == NativeVideoFrameAnalyzerMetric.TEMPORAL_NOISE:
            downsample_width = await context.render_scalar(self.config.downsample_width, int)

            if not 16 <= downsample_width <= 4096:
                raise ValueError(f"'downsample_width' must be between 16 and 4096, got {downsample_width}")

            return {
                "downsample_width": downsample_width,
            }

        if metric == NativeVideoFrameAnalyzerMetric.PAIR_DIFFERENCE:
            downsample_width  = await context.render_scalar(self.config.downsample_width, int)
            move_threshold  = await context.render_scalar(self.config.move_threshold, float)

            if not 16 <= downsample_width <= 4096:
                raise ValueError(f"'downsample_width' must be between 16 and 4096, got {downsample_width}")

            if move_threshold < 0.0:
                raise ValueError(f"'move_threshold' must be non-negative, got {move_threshold}")

            return {
                "downsample_width": downsample_width,
                "move_threshold": move_threshold,
            }

        if metric == NativeVideoFrameAnalyzerMetric.ZERO_PIXEL_RATIO:
            downsample_width = await context.render_scalar(self.config.downsample_width, int)
            exact_match    = await context.render_scalar(self.config.exact_match, bool)

            if not 16 <= downsample_width <= 4096:
                raise ValueError(f"'downsample_width' must be between 16 and 4096, got {downsample_width}")

            return {
                "downsample_width": downsample_width,
                "exact_match":    exact_match,
            }

        raise ValueError(f"Unsupported video frame metric: {metric}")

    async def _analyze(
        self,
        metric: NativeVideoFrameAnalyzerMetric,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if metric == NativeVideoFrameAnalyzerMetric.TEMPORAL_NOISE:
            return await self._analyze_temporal_noise(frames, frame_rate, params, cancellation_token)

        if metric == NativeVideoFrameAnalyzerMetric.PAIR_DIFFERENCE:
            return await self._analyze_pair_difference(frames, frame_rate, params, cancellation_token)

        if metric == NativeVideoFrameAnalyzerMetric.ZERO_PIXEL_RATIO:
            return await self._analyze_zero_pixel_ratio(frames, frame_rate, params, cancellation_token)

        raise ValueError(f"Unsupported video frame metric: {metric}")

    async def _analyze_temporal_noise(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_temporal_noise() -> Dict[str, Any]:
            import numpy as np

            # Mean of per-pair stds of (current - previous). High values mean
            # grainy content (sensor noise, film grain); low values mean smooth
            # inter-frame motion or rendered content.
            pair_stds: List[float] = []
            previous_luma = None
            for frame in collected:
                luma = self._luma_thumbnail(frame, params["downsample_width"])

                if previous_luma is not None:
                    pair_stds.append(float((luma - previous_luma).std()))

                previous_luma = luma

            pair_count = len(pair_stds)

            return {
                "temporal_noise": float(np.mean(pair_stds)) if pair_count else 0.0,
                "pair_count":     pair_count,
                "frame_count":    len(collected),
                "frame_rate":     frame_rate,
                "downsample_width": params["downsample_width"],
            }

        return await self._run_in_executor(_analyze_temporal_noise)

    async def _analyze_pair_difference(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_pair_difference() -> Dict[str, Any]:
            import numpy as np

            pair_mads: List[float] = []
            previous_luma = None

            for frame in collected:
                luma = self._luma_thumbnail(frame, params["downsample_width"])

                if previous_luma is not None:
                    pair_mads.append(float(np.abs(luma - previous_luma).mean()))

                previous_luma = luma

            pair_count = len(pair_mads)

            if pair_count == 0:
                return {
                    "pair_count":        0,
                    "pair_mad_mean":     0.0,
                    "pair_mad_p90":      0.0,
                    "pair_mad_max":      0.0,
                    "moving_pair_ratio": 0.0,
                    "start_end_mad":     0.0,
                    "move_threshold":    params["move_threshold"],
                    "frame_count":       len(collected),
                    "frame_rate":        frame_rate,
                    "downsample_width":    params["downsample_width"],
                }

            pair_mads = np.asarray(pair_mads, dtype=np.float32)

            first_luma = self._luma_thumbnail(collected[0], params["downsample_width"])
            last_luma  = self._luma_thumbnail(collected[-1], params["downsample_width"])
            start_end_mad = float(np.abs(first_luma - last_luma).mean())

            return {
                "pair_count":        pair_count,
                "pair_mad_mean":     float(pair_mads.mean()),
                "pair_mad_p90":      float(np.quantile(pair_mads, 0.9)),
                "pair_mad_max":      float(pair_mads.max()),
                "moving_pair_ratio": float((pair_mads >= params["move_threshold"]).mean()),
                "start_end_mad":     start_end_mad,
                "move_threshold":    params["move_threshold"],
                "frame_count":       len(collected),
                "frame_rate":        frame_rate,
                "downsample_width":    params["downsample_width"],
            }

        return await self._run_in_executor(_analyze_pair_difference)

    async def _analyze_zero_pixel_ratio(
        self,
        frames: ImageArrayValue,
        frame_rate: Optional[float],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        collected = await frames.collect()

        def _analyze_zero_pixel_ratio() -> Dict[str, Any]:
            import numpy as np

            # Share of pixels that never change between consecutive frames —
            # high values signify 2D compositing or motion-graphics animation
            # where the background plate stays pixel-identical.
            zero_ratios: List[float] = []
            previous_luma = None

            for frame in collected:
                luma = self._luma_thumbnail(frame, params["downsample_width"])

                if previous_luma is not None:
                    if params["exact_match"]:
                        zero_ratios.append(float((luma == previous_luma).mean()))
                    else:
                        zero_ratios.append(float((np.abs(luma - previous_luma) < 1.0).mean()))

                previous_luma = luma

            pair_count = len(zero_ratios)

            return {
                "zero_pixel_ratio_mean": float(np.mean(zero_ratios)) if pair_count else 0.0,
                "zero_pixel_ratio_min":  float(np.min(zero_ratios))  if pair_count else 0.0,
                "zero_pixel_ratio_max":  float(np.max(zero_ratios))  if pair_count else 0.0,
                "pair_count":            pair_count,
                "frame_count":           len(collected),
                "exact_match":           params["exact_match"],
                "frame_rate":            frame_rate,
                "downsample_width":        params["downsample_width"],
            }

        return await self._run_in_executor(_analyze_zero_pixel_ratio)

    def _luma_thumbnail(self, frame: PILImage.Image, downsample_width: int):
        """Resample a frame to `downsample_width` on the long axis and return BT.601 luma
        as float32."""
        import numpy as np

        width, height = frame.size

        if width == 0 or height == 0:
            return np.zeros((1, 1), dtype=np.float32)

        if width > downsample_width:
            frame = frame.resize((downsample_width, max(1, int(round(height * downsample_width / width)))))

        return np.asarray(frame.convert("L"), dtype=np.float32)

@register_video_frame_analyzer_driver(VideoFrameAnalyzerDriverType.NATIVE)
class NativeVideoFrameAnalyzerService(VideoFrameAnalyzerDriver):
    def __init__(self, id: str, config: VideoFrameAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "numpy" ]

    async def _run(
        self,
        action: VideoFrameAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeVideoFrameAnalyzerAction(action).run(context)
