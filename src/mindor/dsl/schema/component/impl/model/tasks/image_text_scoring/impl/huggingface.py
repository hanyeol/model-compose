from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ImageTextScoringModelActionConfig
from .common import CommonImageTextScoringModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceImageTextScoringModelArchitecture(str, Enum):
    CLIP   = "clip"
    SIGLIP = "siglip"

class HuggingfaceImageTextScoringModelComponentConfig(CommonImageTextScoringModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    architecture: HuggingfaceImageTextScoringModelArchitecture = Field(..., description="Image-text scoring model architecture.")
    actions: List[ImageTextScoringModelActionConfig] = Field(default_factory=list, description="Actions this image-text scoring component exposes to workflows.")
