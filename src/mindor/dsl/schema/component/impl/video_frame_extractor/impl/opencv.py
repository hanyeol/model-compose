from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OpencvVideoFrameExtractorActionConfig
from .common import CommonVideoFrameExtractorComponentConfig, VideoFrameExtractorDriverType

class OpencvVideoFrameExtractorComponentConfig(CommonVideoFrameExtractorComponentConfig):
    driver: Literal[VideoFrameExtractorDriverType.OPENCV]
    actions: List[OpencvVideoFrameExtractorActionConfig] = Field(default_factory=list)
