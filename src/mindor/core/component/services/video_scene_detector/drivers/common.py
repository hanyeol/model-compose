from __future__ import annotations

from typing import Optional, Dict, List, Union, Any
from collections.abc import AsyncIterable, AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.time import parse_time
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class VideoSceneDetectorAction:
    def __init__(self, config: VideoSceneDetectorActionConfig):
        self.config: VideoSceneDetectorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(video, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(video, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_videos, params, streaming, loop)
                    for result in batch_results:
                        if isinstance(result, AsyncIterable):
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
                batch_results = await self._process_batch(batch_videos, params, streaming, loop)
                for result in batch_results:
                    if isinstance(result, AsyncIterable):
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        detector   = await context.render_variable(self.config.detector) if self.config.detector else None
        threshold  = float(await context.render_variable(self.config.threshold)) if self.config.threshold is not None else None
        start_time = parse_time(await context.render_variable(self.config.start_time)) if self.config.start_time else None
        end_time   = parse_time(await context.render_variable(self.config.end_time)) if self.config.end_time else None

        return {
            "detector":   detector,
            "threshold":  threshold,
            "start_time": start_time,
            "end_time":   end_time,
        }

    async def _process_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> List[Optional[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]]]:
        return await asyncio.gather(*[
            self._process(video, params, streaming, loop) for video in videos
        ])

    async def _process(
        self,
        video: MediaSource,
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Optional[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]]:
        if video is None:
            logging.debug("Video scene detector skipped because no video was provided.")
            return None

        return await self._detect(
            video,
            params["detector"],
            params["threshold"],
            params["start_time"],
            params["end_time"],
            streaming,
            loop,
        )

    @abstractmethod
    async def _detect(
        self,
        video: MediaSource,
        detector: Optional[str],
        threshold: Optional[float],
        start_time: Optional[float],
        end_time: Optional[float],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]:
        pass
