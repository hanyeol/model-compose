from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import VideoTextScoringModelActionConfig
from .common import CommonVideoTextScoringModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceVideoTextScoringModelArchitecture(str, Enum):
    XCLIP = "xclip"

class HuggingfaceVideoTextScoringModelComponentConfig(CommonVideoTextScoringModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    architecture: HuggingfaceVideoTextScoringModelArchitecture = Field(..., description="Video-text scoring model architecture.")
    actions: List[VideoTextScoringModelActionConfig] = Field(default_factory=list, description="Actions this video-text scoring component exposes to workflows.")
