from __future__ import annotations

from typing import Optional, Dict, List, Union, Any
from collections.abc import AsyncIterable, AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.utils.iterators import BatchSourceIterator, StreamChunkIterator
from mindor.core.utils.streaming.media import MediaSource
from mindor.core.utils.time import parse_timecode
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class VideoFrameExtractorAction:
    def __init__(self, config: VideoFrameExtractorActionConfig):
        self.config: VideoFrameExtractorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(video, (list, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(video, AsyncIterator):
            async def _stream_output_generator():
                async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_videos, params, streaming, loop)
                    for result in batch_results:
                        if isinstance(result, AsyncIterable):
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator())
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_videos, params, streaming, loop)
                for result in batch_results:
                    if isinstance(result, AsyncIterable):
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator()))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        frame_interval  = int(await context.render_variable(self.config.frame_interval))
        start_time      = parse_timecode(await context.render_variable(self.config.start_time)) if self.config.start_time else None
        end_time        = parse_timecode(await context.render_variable(self.config.end_time)) if self.config.end_time else None
        max_frame_count = int(await context.render_variable(self.config.max_frame_count)) if self.config.max_frame_count is not None else None

        if frame_interval < 1:
            raise ValueError(f"'frame_interval' must be >= 1, got {frame_interval}")

        if max_frame_count is not None and max_frame_count < 1:
            raise ValueError(f"'max_frame_count' must be >= 1, got {max_frame_count}")

        return {
            "frame_interval":  frame_interval,
            "start_time":      start_time,
            "end_time":        end_time,
            "max_frame_count": max_frame_count,
        }

    async def _process_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> List[Optional[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]]]:
        return await asyncio.gather(*[
            self._process(video, params, streaming, loop) for video in videos
        ])

    async def _process(
        self,
        video: MediaSource,
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Optional[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]]:
        if video is None:
            logging.debug("Video frame extractor skipped because no video was provided.")
            return None

        return await self._extract(
            video,
            params["frame_interval"],
            params["start_time"],
            params["end_time"],
            params["max_frame_count"],
            streaming,
            loop,
        )

    @abstractmethod
    async def _extract(
        self,
        video: MediaSource,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]:
        pass
