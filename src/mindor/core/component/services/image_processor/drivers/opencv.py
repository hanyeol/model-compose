from __future__ import annotations

from typing import Optional, Union, Tuple, Dict, List, Any
from mindor.dsl.schema.component import ImageProcessorComponentConfig
from mindor.dsl.schema.action import (
    ImageProcessorActionConfig,
    OpenCvImageProcessorActionMethod,
)
from mindor.core.foundation.variable.image import ImageArrayValue
from ..base import ImageProcessorDriver, ImageProcessorDriverType, register_image_processor_driver
from ..base import ComponentActionContext
from .common import ImageProcessorAction
from PIL import Image as PILImage

class OpenCvImageProcessorAction(ImageProcessorAction):
    async def _prepare_input(self, method: OpenCvImageProcessorActionMethod, context: ComponentActionContext) -> Any:
        return await context.render_image(self.config.image)

    async def _resolve_params(self, method: OpenCvImageProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == OpenCvImageProcessorActionMethod.CANNY:
            low_threshold  = await context.render_scalar(self.config.low_threshold, int)
            high_threshold = await context.render_scalar(self.config.high_threshold, int)

            if low_threshold is None or high_threshold is None:
                raise ValueError("'low_threshold' and 'high_threshold' must both be specified for 'canny' method")

            if low_threshold < 0 or high_threshold < 0:
                raise ValueError("Canny thresholds must be non-negative")

            if low_threshold > high_threshold:
                raise ValueError(f"'low_threshold' ({low_threshold}) must be <= 'high_threshold' ({high_threshold})")

            return { "low_threshold": low_threshold, "high_threshold": high_threshold }

        raise ValueError(f"Unsupported image processing action method: {method}")

    async def _process(self, method: OpenCvImageProcessorActionMethod, image: Union[PILImage.Image, ImageArrayValue], params: Dict[str, Any]) -> PILImage.Image:
        if method == OpenCvImageProcessorActionMethod.CANNY:
            return await self._canny(image, params)

        raise ValueError(f"Unsupported image processing action method: {method}")

    async def _canny(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _canny() -> PILImage.Image:
            import cv2
            import numpy as np

            rgb = image.convert("RGB")
            array = np.array(rgb)
            gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, params["low_threshold"], params["high_threshold"])

            return PILImage.fromarray(edges, mode="L")

        return await self._run_in_executor(_canny)

@register_image_processor_driver(ImageProcessorDriverType.OPENCV)
class OpenCvImageProcessorService(ImageProcessorDriver):
    def __init__(self, id: str, config: ImageProcessorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            "opencv-python",
            "numpy",
        ]

    async def _run(self, action: ImageProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await OpenCvImageProcessorAction(action).run(context)
