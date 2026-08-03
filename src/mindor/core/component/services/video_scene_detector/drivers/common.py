from __future__ import annotations

from typing import Optional, Dict, List, Union, Any
from collections.abc import AsyncIterable, AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class VideoSceneDetectorAction(ComponentAction):
    def __init__(self, config: VideoSceneDetectorActionConfig):
        self.config: VideoSceneDetectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(video, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(video, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                    batch_results = await self._detect_batch(batch_videos, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                batch_results = await self._detect_batch(batch_videos, params, streaming, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        detector   = await context.render_variable(self.config.detector) if self.config.detector else None
        threshold  = await context.render_scalar(self.config.threshold, float)
        start_time = await context.render_time(self.config.start_time)
        end_time   = await context.render_time(self.config.end_time)

        return {
            "detector":   detector,
            "threshold":  threshold,
            "start_time": start_time,
            "end_time":   end_time,
        }

    @abstractmethod
    async def _detect_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]]:
        pass
