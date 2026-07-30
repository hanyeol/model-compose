from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from ....action.media import MediaComponentAction
from ..base import ComponentActionContext

class VideoConverterAction(MediaComponentAction):
    def __init__(self, config: VideoConverterActionConfig):
        self.config: VideoConverterActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(video, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(video, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                    batch_results = await self._convert_batch(batch_videos, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                batch_results = await self._convert_batch(batch_videos, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        encoding = await self._resolve_encoding_params(context, self.config.encoding) if self.config.encoding else VideoAudioEncodingParams()

        return {
            "encoding": encoding,
        }

    @abstractmethod
    async def _convert_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        pass
