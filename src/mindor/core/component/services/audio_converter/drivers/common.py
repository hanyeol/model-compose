from __future__ import annotations

from mindor.dsl.schema.action import AudioConverterActionConfig

class AudioConverterAction:
    def __init__(self, config: AudioConverterActionConfig):
        self.config: AudioConverterActionConfig = config
