from __future__ import annotations

from typing import Dict, Tuple, Any
from mindor.dsl.schema.action import VideoConverterActionConfig, VideoSourceConfig
from ..base import ComponentActionContext

class VideoConverterAction:
    def __init__(self, config: VideoConverterActionConfig):
        self.config: VideoConverterActionConfig = config

    async def _render_video(self, context: ComponentActionContext) -> Tuple[Any, Dict[str, Any]]:
        if isinstance(self.config.video, VideoSourceConfig):
            data         = await context.render_variable(self.config.video.data)
            format       = await context.render_variable(self.config.video.format) if self.config.video.format else None
            resolution   = await context.render_variable(self.config.video.resolution) if self.config.video.resolution else None
            fps          = await context.render_variable(self.config.video.fps) if self.config.video.fps else None
            pixel_format = await context.render_variable(self.config.video.pixel_format) if self.config.video.pixel_format else None
            attrs: Dict[str, Any] = {}
            if format is not None:        attrs["format"] = format
            if resolution is not None:    attrs["resolution"] = resolution
            if fps is not None:           attrs["fps"] = fps
            if pixel_format is not None:  attrs["pixel_format"] = pixel_format
            return data, attrs
        return await context.render_variable(self.config.video), {}
