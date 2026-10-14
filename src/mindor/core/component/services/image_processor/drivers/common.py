from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageProcessorActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ..base import ComponentActionContext
from ....action.base import ComponentAction
from PIL import Image as PILImage
import asyncio

class ImageProcessorAction(ComponentAction):
    """Driver-agnostic skeleton for image-processor actions.

    Subclasses declare their own method set and override `_prepare_input`,
    `_resolve_params`, and `_process` to dispatch on that set — common.py
    does not know which methods exist, only how to stream/batch them.
    """
    def __init__(self, config: ImageProcessorActionConfig):
        self.config: ImageProcessorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(self.config.method, batch_images, params)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(image, StreamChunkIterator) and image.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._process_batch(self.config.method, batch_images, params)
                results.extend(batch_results)

            result = results[0] if is_single_input else results

            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _process_batch(
        self,
        method: Any,
        images: Union[List[Optional[PILImage.Image]], List[Optional[ImageArrayValue]]],
        params: Dict[str, Any],
    ) -> List[Optional[PILImage.Image]]:
        async def _process(image: Optional[Union[PILImage.Image, ImageArrayValue]]) -> Optional[PILImage.Image]:
            if image is None:
                logging.debug("Image processor (%s) skipped because no image was provided.", method)
                return None

            return await self._process(method, image, params)

        return await asyncio.gather(*[ _process(image) for image in images ])

    @abstractmethod
    async def _prepare_input(self, method: Any, context: ComponentActionContext) -> Any:
        pass

    @abstractmethod
    async def _resolve_params(self, method: Any, context: ComponentActionContext) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _process(self, method: Any, image: Union[PILImage.Image, ImageArrayValue], params: Dict[str, Any]) -> PILImage.Image:
        pass
