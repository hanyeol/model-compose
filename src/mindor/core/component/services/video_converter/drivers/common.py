from __future__ import annotations

from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.utils.video import create_video_source
from mindor.core.utils.media import MediaSource
from ..base import ComponentActionContext

class VideoConverterAction:
    def __init__(self, config: VideoConverterActionConfig):
        self.config: VideoConverterActionConfig = config

    async def _render_video(self, context: ComponentActionContext) -> MediaSource:
        return create_video_source(await context.render_variable(self.config.video))
