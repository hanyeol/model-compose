from __future__ import annotations

from typing import Any, Dict, List, Optional
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VisionTextEncodingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction
from PIL import Image as PILImage
import asyncio

class VisionTextEncodingTaskAction(ModelTaskComponentAction):
    def __init__(self, config: VisionTextEncodingModelActionConfig):
        self.config: VisionTextEncodingModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        text       = await context.render_text(self.config.text)
        images     = await context.render_image_array(self.config.images, single_as_array=True, item_is_list=True) if self.config.images is not None else None
        frames     = await context.render_image_array(self.config.frames, single_as_array=True, item_is_list=True) if self.config.frames is not None else None
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(text, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts, batch_images, batch_frames in BatchSourceIterator((text, images, frames), batch_size=batch_size or 1):
                    batch_results = await self._encode_batch(batch_texts, batch_images, batch_frames, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(text, StreamChunkIterator) and text.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_texts, batch_images, batch_frames in BatchSourceIterator((text, images, frames), batch_size=batch_size or 1):
                batch_results = await self._encode_batch(batch_texts, batch_images, batch_frames, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        layer              = await context.render_scalar(self.config.params.layer, int)
        add_special_tokens = await context.render_scalar(self.config.params.add_special_tokens, bool)
        max_length         = await context.render_scalar(self.config.params.max_length, int)

        return {
            "layer":              layer,
            "add_special_tokens": add_special_tokens,
            "max_length":         max_length,
        }

    async def _encode_batch(
        self,
        texts: List[str],
        images: List[Any],
        frames: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        images = [ (await item.collect() if item is not None else []) for item in images ]
        frames = [ (await item.collect() if item is not None else []) for item in frames ]

        return await asyncio.gather(*[
            self._encode(text, images[index], frames[index], params, cancellation_token)
            for index, text in enumerate(texts)
        ])

    @abstractmethod
    async def _encode(
        self,
        text: str,
        images: List[PILImage.Image],
        frames: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        pass
