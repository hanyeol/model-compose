from __future__ import annotations

from typing import Optional, Any
from mindor.dsl.schema.action import AudioConverterActionConfig, AudioSourceConfig
from ..base import ComponentActionContext

class AudioSource:
    def __init__(self, path: Optional[str], data: Any, format: Optional[str], sample_rate: Optional[int], channels: Optional[int]):
        self.path        = path
        self.data        = data
        self.format      = format
        self.sample_rate = sample_rate
        self.channels    = channels

class AudioConverterAction:
    def __init__(self, config: AudioConverterActionConfig):
        self.config: AudioConverterActionConfig = config

    async def _render_source(self, context: ComponentActionContext) -> AudioSource:
        source = self.config.source
        if isinstance(source, AudioSourceConfig):
            path        = await context.render_variable(source.path) if source.path else None
            data        = await context.render_variable(source.data) if source.data else None
            format      = await context.render_variable(source.format) if source.format else None
            sample_rate = await context.render_variable(source.sample_rate) if isinstance(source.sample_rate, str) else source.sample_rate
            channels    = await context.render_variable(source.channels) if isinstance(source.channels, str) else source.channels
        else:
            path        = await context.render_variable(source)
            data        = None
            format      = None
            sample_rate = None
            channels    = None
        return AudioSource(path, data, format, sample_rate, channels)
