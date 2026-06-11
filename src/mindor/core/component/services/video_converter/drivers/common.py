from __future__ import annotations

from mindor.dsl.schema.action import VideoConverterActionConfig

class VideoConverterAction:
    def __init__(self, config: VideoConverterActionConfig):
        self.config: VideoConverterActionConfig = config
