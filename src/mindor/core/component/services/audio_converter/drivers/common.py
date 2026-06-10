from __future__ import annotations

from mindor.dsl.schema.action import AudioConverterActionConfig
from mindor.core.utils.audio import create_audio_source
from mindor.core.utils.media import MediaSource
from ..base import ComponentActionContext

class AudioConverterAction:
    def __init__(self, config: AudioConverterActionConfig):
        self.config: AudioConverterActionConfig = config

    async def _render_audio(self, context: ComponentActionContext) -> MediaSource:
        return create_audio_source(await context.render_variable(self.config.audio))
