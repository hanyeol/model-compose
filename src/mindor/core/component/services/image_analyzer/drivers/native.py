from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Dict, Any
from mindor.dsl.schema.component import ImageAnalyzerComponentConfig, ImageAnalyzerDriver
from mindor.dsl.schema.action import ImageAnalyzerActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from ..base import ImageAnalyzerService, register_image_analyzer_service
from ..base import ComponentActionContext
from .common import ImageAnalyzerAction

if TYPE_CHECKING:
    from PIL import Image as PILImage

class NativeImageAnalyzerAction(ImageAnalyzerAction):
    async def _analyze_brightness(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_brightness() -> Dict[str, Any]:
            import numpy as np

            # Pillow's `convert("L")` applies ITU-R BT.601 luma coefficients
            # (0.299 R + 0.587 G + 0.114 B), which every metric below assumes.
            luma = np.asarray(image.convert("L"), dtype=np.float32)

            return {
                "mean_brightness": float(luma.mean()),
                "min_brightness":  float(luma.min()),
                "max_brightness":  float(luma.max()),
                "std_brightness":  float(luma.std()),
                "width":           image.width,
                "height":          image.height,
            }

        return await self._run_in_executor(_analyze_brightness)

    async def _analyze_contrast(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_contrast() -> Dict[str, Any]:
            import numpy as np

            luma = np.asarray(image.convert("L"), dtype=np.float32)

            # RMS contrast: standard deviation of pixel luma — a scale-invariant
            # measure that beats naive (max-min) for photographic images where a
            # few outlier pixels would otherwise dominate.
            rms_contrast = float(luma.std())

            # Michelson contrast on percentile-clipped extremes, so a single hot
            # pixel doesn't push the number to its ceiling.
            low = float(np.percentile(luma, 1))
            high = float(np.percentile(luma, 99))
            denominator = high + low
            michelson_contrast = (high - low) / denominator if denominator else 0.0

            return {
                "rms_contrast":       rms_contrast,
                "michelson_contrast": michelson_contrast,
                "luma_percentile_1":  low,
                "luma_percentile_99": high,
                "width":              image.width,
                "height":             image.height,
            }

        return await self._run_in_executor(_analyze_contrast)

    async def _analyze_sharpness(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_sharpness() -> Dict[str, Any]:
            import numpy as np

            luma = np.asarray(image.convert("L"), dtype=np.float32)

            # Laplacian variance is the standard cheap blur detector: apply a 3x3
            # Laplacian kernel, take the variance of the response. Low variance
            # means the image has little high-frequency detail, i.e. it's blurred
            # or out of focus. The classic threshold is ~100 for 8-bit imagery,
            # but the "right" value depends on content.
            laplacian = np.zeros_like(luma, dtype=np.float32)
            laplacian[1:-1, 1:-1] = (
                -4.0 * luma[1:-1, 1:-1]
                + luma[:-2, 1:-1]
                + luma[2:, 1:-1]
                + luma[1:-1, :-2]
                + luma[1:-1, 2:]
            )
            variance = float(laplacian.var())

            return {
                "laplacian_variance": variance,
                "blur_threshold":     params["blur_threshold"],
                "is_blurry":          variance < params["blur_threshold"],
                "width":              image.width,
                "height":             image.height,
            }

        return await self._run_in_executor(_analyze_sharpness)

    async def _analyze_exposure(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _analyze_exposure() -> Dict[str, Any]:
            import numpy as np

            shadow_threshold    = params["shadow_threshold"]
            highlight_threshold = params["highlight_threshold"]

            luma = np.asarray(image.convert("L"), dtype=np.float32)
            total_pixels = luma.size

            shadow_clipped = int((luma <= shadow_threshold).sum())
            highlight_clipped = int((luma >= highlight_threshold).sum())

            return {
                "shadow_threshold":         shadow_threshold,
                "highlight_threshold":      highlight_threshold,
                "shadow_clipped_pixels":    shadow_clipped,
                "highlight_clipped_pixels": highlight_clipped,
                "shadow_clipped_ratio":     shadow_clipped / total_pixels if total_pixels else 0.0,
                "highlight_clipped_ratio":  highlight_clipped / total_pixels if total_pixels else 0.0,
                "mean_brightness":          float(luma.mean()),
                "width":                    image.width,
                "height":                   image.height,
            }

        return await self._run_in_executor(_analyze_exposure)

@register_image_analyzer_service(ImageAnalyzerDriver.NATIVE)
class NativeImageAnalyzerService(ImageAnalyzerService):
    def __init__(self, id: str, config: ImageAnalyzerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "numpy" ]

    async def _run(
        self,
        action: ImageAnalyzerActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeImageAnalyzerAction(action).run(context)
