from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoTextScoringModelActionConfig
from ..common import CommonVideoTextScoringModelComponentConfig
from .common import VideoTextScoringModelFamily
from ....common import ModelDriverType

class CustomVideoTextScoringModelComponentConfig(CommonVideoTextScoringModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: VideoTextScoringModelFamily = Field(..., description="Model family selecting the custom video-text scoring implementation.")
    actions: List[VideoTextScoringModelActionConfig] = Field(default_factory=list, description="Actions this video-text scoring component exposes to workflows.")
