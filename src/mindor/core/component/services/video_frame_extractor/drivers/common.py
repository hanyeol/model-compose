from __future__ import annotations

from typing import Optional, Dict, List, Union, Any

from collections.abc import AsyncIterable, AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class VideoFrameExtractorAction(ComponentAction):
    def __init__(self, config: VideoFrameExtractorActionConfig):
        self.config: VideoFrameExtractorActionConfig = config

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
                    batch_results = await self._extract_batch(batch_videos, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                batch_results = await self._extract_batch(batch_videos, params, streaming, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        frame_interval  = await context.render_scalar(self.config.frame_interval, int)
        keyframe_only   = await context.render_scalar(self.config.keyframe_only, bool)
        start_time      = await context.render_scalar(self.config.start_time, "time")
        end_time        = await context.render_scalar(self.config.end_time, "time")
        max_frame_count = await context.render_scalar(self.config.max_frame_count, int)
        filename_format = await context.render_variable(self.config.filename_format)

        if frame_interval < 1:
            raise ValueError(f"'frame_interval' must be >= 1, got {frame_interval}")

        if max_frame_count is not None and max_frame_count < 1:
            raise ValueError(f"'max_frame_count' must be >= 1, got {max_frame_count}")

        return {
            "frame_interval":  frame_interval,
            "keyframe_only":   keyframe_only,
            "start_time":      start_time,
            "end_time":        end_time,
            "max_frame_count": max_frame_count,
            "filename_format": filename_format,
        }

    @abstractmethod
    async def _extract_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]]:
        pass
