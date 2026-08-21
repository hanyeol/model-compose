from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageAnalyzerActionConfig
from mindor.dsl.schema.action.impl.image_analyzer.impl.common import ImageAnalyzerMetric
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import asyncio

if TYPE_CHECKING:
    from PIL import Image as PILImage

class ImageBrightness(AtomicDict):
    def __log__(self) -> str:
        return f"<ImageBrightness mean={self.get('mean_brightness')}>"

class ImageContrast(AtomicDict):
    def __log__(self) -> str:
        return f"<ImageContrast rms={self.get('rms_contrast')}>"

class ImageSharpness(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<ImageSharpness variance={self.get('laplacian_variance')} "
            f"blurry={self.get('is_blurry')}>"
        )

class ImageExposure(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<ImageExposure shadow_ratio={self.get('shadow_clipped_ratio', 0.0):.4f} "
            f"highlight_ratio={self.get('highlight_clipped_ratio', 0.0):.4f}>"
        )

class ImageAnalyzerAction(ComponentAction):
    def __init__(self, config: ImageAnalyzerActionConfig):
        self.config: ImageAnalyzerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.metric, context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._analyze_batch(batch_images, self.config.metric, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._analyze_batch(batch_images, self.config.metric, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, metric: ImageAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        if metric == ImageAnalyzerMetric.BRIGHTNESS:
            return {}

        if metric == ImageAnalyzerMetric.CONTRAST:
            return {}

        if metric == ImageAnalyzerMetric.SHARPNESS:
            blur_threshold = await context.render_scalar(self.config.blur_threshold, float)

            return {
                "blur_threshold": blur_threshold,
            }

        if metric == ImageAnalyzerMetric.EXPOSURE:
            shadow_threshold    = await context.render_scalar(self.config.shadow_threshold, int)
            highlight_threshold = await context.render_scalar(self.config.highlight_threshold, int)

            return {
                "shadow_threshold":    shadow_threshold,
                "highlight_threshold": highlight_threshold,
            }

        raise ValueError(f"Unsupported image metric: {metric}")

    async def _analyze_batch(
        self,
        images: List[PILImage.Image],
        metric: ImageAnalyzerMetric,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[dict]:
        return await asyncio.gather(*[
            self._analyze(metric, image, params, cancellation_token) for image in images
        ])

    async def _analyze(
        self,
        metric: ImageAnalyzerMetric,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> dict:
        if metric == ImageAnalyzerMetric.BRIGHTNESS:
            return await self._analyze_brightness(image, params, cancellation_token)

        if metric == ImageAnalyzerMetric.CONTRAST:
            return await self._analyze_contrast(image, params, cancellation_token)

        if metric == ImageAnalyzerMetric.SHARPNESS:
            return await self._analyze_sharpness(image, params, cancellation_token)

        if metric == ImageAnalyzerMetric.EXPOSURE:
            return await self._analyze_exposure(image, params, cancellation_token)

        raise ValueError(f"Unsupported image metric: {metric}")

    @abstractmethod
    async def _analyze_brightness(self, image: PILImage.Image, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> dict:
        pass

    @abstractmethod
    async def _analyze_contrast(self, image: PILImage.Image, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> dict:
        pass

    @abstractmethod
    async def _analyze_sharpness(self, image: PILImage.Image, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> dict:
        pass

    @abstractmethod
    async def _analyze_exposure(self, image: PILImage.Image, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> dict:
        pass
