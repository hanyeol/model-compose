from __future__ import annotations

from typing import Optional, Any
from mindor.dsl.schema.action import VideoConverterActionConfig, VideoSourceConfig
from ..base import ComponentActionContext

class VideoSource:
    def __init__(self, path: Optional[str], data: Any, format: Optional[str], resolution: Optional[str], fps: Optional[str], pixel_format: Optional[str]):
        self.path         = path
        self.data         = data
        self.format       = format
        self.resolution   = resolution
        self.fps          = fps
        self.pixel_format = pixel_format

class VideoConverterAction:
    def __init__(self, config: VideoConverterActionConfig):
        self.config: VideoConverterActionConfig = config

    async def _render_source(self, context: ComponentActionContext) -> VideoSource:
        source = self.config.source
        if isinstance(source, VideoSourceConfig):
            path         = await context.render_variable(source.path) if source.path else None
            data         = await context.render_variable(source.data) if source.data else None
            format       = await context.render_variable(source.format) if source.format else None
            resolution   = await context.render_variable(source.resolution) if source.resolution else None
            fps          = await context.render_variable(source.fps) if source.fps else None
            pixel_format = await context.render_variable(source.pixel_format) if source.pixel_format else None
        else:
            path         = await context.render_variable(source)
            data         = None
            format       = None
            resolution   = None
            fps          = None
            pixel_format = None
        return VideoSource(path, data, format, resolution, fps, pixel_format)
