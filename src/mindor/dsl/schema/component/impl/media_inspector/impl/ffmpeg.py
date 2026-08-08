from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegMediaInspectorActionConfig
from .common import CommonMediaInspectorComponentConfig, MediaInspectorDriver

class FFmpegMediaInspectorComponentConfig(CommonMediaInspectorComponentConfig):
    driver: Literal[MediaInspectorDriver.FFMPEG]
    actions: List[FFmpegMediaInspectorActionConfig] = Field(default_factory=list)
