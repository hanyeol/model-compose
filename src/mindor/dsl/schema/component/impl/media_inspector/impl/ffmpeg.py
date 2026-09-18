from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegMediaInspectorActionConfig
from .common import CommonMediaInspectorComponentConfig, MediaInspectorDriverType

class FFmpegMediaInspectorComponentConfig(CommonMediaInspectorComponentConfig):
    driver: Literal[MediaInspectorDriverType.FFMPEG]
    actions: List[FFmpegMediaInspectorActionConfig] = Field(default_factory=list)
