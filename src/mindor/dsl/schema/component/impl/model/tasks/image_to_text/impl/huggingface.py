from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ImageToTextModelActionConfig
from .common import CommonImageToTextModelComponentConfig
from ...common import ModelDriver

class HuggingfaceImageToTextModelArchitecture(str, Enum):
    AUTO       = "auto"
    BLIP       = "blip"
    BLIP2      = "blip2"
    GIT        = "git"
    PIX2STRUCT = "pix2struct"
    DONUT      = "donut"
    KOSMOS2    = "kosmos2"

class HuggingfaceImageToTextModelComponentConfig(CommonImageToTextModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    architecture: HuggingfaceImageToTextModelArchitecture = Field(default=HuggingfaceImageToTextModelArchitecture.AUTO, description="Model architecture.")
    actions: List[ImageToTextModelActionConfig] = Field(default_factory=list)
