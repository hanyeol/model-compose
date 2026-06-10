from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from mindor.dsl.schema.action import AudioConverterActionConfig, AudioSourceConfig
from ..base import ComponentActionContext

class AudioConverterAction:
    def __init__(self, config: AudioConverterActionConfig):
        self.config: AudioConverterActionConfig = config

    async def _render_audio(self, context: ComponentActionContext) -> Tuple[Any, Dict[str, Any]]:
        if isinstance(self.config.audio, AudioSourceConfig):
            data        = await context.render_variable(self.config.audio.data)
            format      = await context.render_variable(self.config.audio.format) if self.config.audio.format else None
            sample_rate = await context.render_variable(self.config.audio.sample_rate) if isinstance(self.config.audio.sample_rate, str) else self.config.audio.sample_rate
            channels    = await context.render_variable(self.config.audio.channels) if isinstance(self.config.audio.channels, str) else self.config.audio.channels
            attrs: Dict[str, Any] = {}
            if format is not None:        attrs["format"] = format
            if sample_rate is not None:   attrs["sample_rate"] = sample_rate
            if channels is not None:      attrs["channels"] = channels
            return data, attrs
        return await context.render_variable(self.config.audio), {}
