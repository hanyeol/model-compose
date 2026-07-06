from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ImageTextToTextModelActionConfig
from .common import CommonImageTextToTextModelComponentConfig
from ...common import ModelDriver

class HuggingfaceImageTextToTextModelArchitecture(str, Enum):
    AUTO       = "auto"
    QWEN2_VL   = "qwen2-vl"
    QWEN2_5_VL = "qwen2.5-vl"
    LLAVA      = "llava"
    LLAVA_NEXT = "llava-next"
    IDEFICS3   = "idefics3"
    INTERNVL   = "internvl"

class HuggingfaceImageTextToTextModelComponentConfig(CommonImageTextToTextModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    architecture: HuggingfaceImageTextToTextModelArchitecture = Field(default=HuggingfaceImageTextToTextModelArchitecture.AUTO, description="Vision-language model architecture.")
    actions: List[ImageTextToTextModelActionConfig] = Field(default_factory=list)
