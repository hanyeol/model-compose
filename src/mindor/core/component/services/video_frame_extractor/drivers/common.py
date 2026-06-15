from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.utils.iterator import AsyncSourceIterator
from mindor.core.utils.media import MediaSource
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

        is_stream_input  = isinstance(video, AsyncIterator)
        is_stream_output = context.contains_variable_reference("result[]", self.config.output)
        is_direct_output = not self.config.output or self.config.output == "${result}"
        is_stream_mode   = streaming or is_stream_output or (is_stream_input and is_direct_output)

        if is_stream_mode:
            async def _stream_output_generator():
                async for batch_videos in AsyncSourceIterator(video, batch_size=batch_size or 1):
                    batched_frames = await self._process_batch(batch_videos, context)
                    for frames in batched_frames:
                        context.register_source("result[]", frames)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else frames

            return _stream_output_generator()

        is_single_input: bool = not isinstance(video, (list, AsyncIterator))
        results = []
        async for batch_videos in AsyncSourceIterator(video, batch_size=batch_size or 1):
            batched_frames = await self._process_batch(batch_videos, context)
            results.extend(batched_frames)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _process_batch(self, videos: List[MediaSource], context: ComponentActionContext) -> List[Optional[Dict[str, Any]]]:
        params = await self._resolve_params(context)

        return await asyncio.gather(*[
            self._process(video, params) for video in videos
        ])

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

    async def _process(self, video: MediaSource, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if video is None:
            logging.debug("Video frame extractor skipped because no video was provided.")
            return None

        frames = await self._extract(
            video,
            params["frame_interval"],
            params["start_time"],
            params["end_time"],
            params["max_frame_count"],
        )

        return { "frames": frames, "frame_count": len(frames) }

    @abstractmethod
    async def _extract(
        self,
        video: MediaSource,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
    ) -> List[Dict[str, Any]]:
        pass
