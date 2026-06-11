from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import abstractmethod
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.utils.media import MediaSource
from mindor.core.utils.time import parse_timecode
from ..base import ComponentActionContext
import asyncio

class VideoFrameExtractorAction:
    def __init__(self, config: VideoFrameExtractorActionConfig):
        self.config: VideoFrameExtractorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        video           = await context.render_video(self.config.video)
        frame_interval  = int(await context.render_variable(self.config.frame_interval))
        start_time      = parse_timecode(await context.render_variable(self.config.start_time)) if self.config.start_time else None
        end_time        = parse_timecode(await context.render_variable(self.config.end_time)) if self.config.end_time else None
        max_frame_count = int(await context.render_variable(self.config.max_frame_count)) if self.config.max_frame_count is not None else None

        if frame_interval < 1:
            raise ValueError(f"frame_interval must be >= 1, got {frame_interval}")

        if max_frame_count is not None and max_frame_count < 1:
            raise ValueError(f"max_frame_count must be >= 1, got {max_frame_count}")

        frames = await self._extract(video, frame_interval, start_time, end_time, max_frame_count)

        result = { "frames": frames, "frame_count": len(frames) }
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

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
