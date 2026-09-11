from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TalkingHeadModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class TalkingHeadTaskAction(ComponentAction):
    def __init__(self, config: TalkingHeadModelActionConfig):
        self.config: TalkingHeadModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        source = (image, audio)

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images, batch_audios in BatchSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_images, batch_audios, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[VideoStreamResource] = []
            async for batch_images, batch_audios in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_images, batch_audios, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        fps  = await context.render_variable(self.config.params.fps)
        seed = await context.render_variable(self.config.seed)

        return {
            "fps":  fps,
            "seed": seed,
        }

    @abstractmethod
    async def _generate_batch(
        self,
        images: List[PILImage.Image],
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        pass
