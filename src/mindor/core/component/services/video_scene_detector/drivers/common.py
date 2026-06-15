from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.utils.iterator import AsyncSourceIterator
from mindor.core.utils.media import MediaSource
from mindor.core.utils.time import parse_timecode
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class VideoSceneDetectorAction:
    def __init__(self, config: VideoSceneDetectorActionConfig):
        self.config: VideoSceneDetectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)

        is_stream_input  = isinstance(video, AsyncIterator)
        is_stream_output = context.contains_variable_reference("result[]", self.config.output)
        is_direct_output = not self.config.output or self.config.output == "${result}"
        is_stream_mode   = is_stream_output or (is_stream_input and is_direct_output)

        if is_stream_mode:
            async def _stream_output_generator():
                async for batch_videos in AsyncSourceIterator(video, batch_size=batch_size or 1):
                    processed_videos = await self._process_batch(batch_videos, context)
                    for processed_video in processed_videos:
                        context.register_source("result[]", processed_video)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else processed_video

            return _stream_output_generator()

        is_single_input: bool = not isinstance(video, (list, AsyncIterator))
        results = []
        async for batch_videos in AsyncSourceIterator(video, batch_size=batch_size or 1):
            processed_videos = await self._process_batch(batch_videos, context)
            results.extend(processed_videos)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _process_batch(self, videos: List[MediaSource], context: ComponentActionContext) -> List[Optional[Dict[str, Any]]]:
        params = await self._resolve_params(context)

        return await asyncio.gather(*[
            self._process(video, params) for video in videos
        ])

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        detector   = await context.render_variable(self.config.detector) if self.config.detector else None
        threshold  = float(await context.render_variable(self.config.threshold)) if self.config.threshold is not None else None
        start_time = parse_timecode(await context.render_variable(self.config.start_time)) if self.config.start_time else None
        end_time   = parse_timecode(await context.render_variable(self.config.end_time)) if self.config.end_time else None

        return {
            "detector":   detector,
            "threshold":  threshold,
            "start_time": start_time,
            "end_time":   end_time,
        }

    async def _process(self, video: MediaSource, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if video is None:
            logging.debug("Video scene detector skipped because no video was provided.")
            return None

        return await self._detect(
            video,
            params["detector"],
            params["threshold"],
            params["start_time"],
            params["end_time"],
        )

    @abstractmethod
    async def _detect(
        self,
        video: MediaSource,
        detector: Optional[str],
        threshold: Optional[float],
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> Dict[str, Any]:
        pass
