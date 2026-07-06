from typing import Literal, List, Union, Annotated
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import (
    SdxlHuggingfaceImageGenerationModelActionConfig,
    FluxHuggingfaceImageGenerationModelActionConfig,
    HunyuanImageHuggingfaceImageGenerationModelActionConfig,
)
from .common import CommonImageGenerationModelComponentConfig
from ...common import ModelDriver

class HuggingfaceImageGenerationModelArchitecture(str, Enum):
    SDXL          = "sdxl"
    FLUX          = "flux"
    HUNYUAN_IMAGE = "hunyuan-image"

class CommonHuggingfaceImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]

class SdxlHuggingfaceImageGenerationModelComponentConfig(CommonHuggingfaceImageGenerationModelComponentConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.SDXL]
    actions: List[SdxlHuggingfaceImageGenerationModelActionConfig] = Field(default_factory=list)

class FluxHuggingfaceImageGenerationModelComponentConfig(CommonHuggingfaceImageGenerationModelComponentConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.FLUX]
    actions: List[FluxHuggingfaceImageGenerationModelActionConfig] = Field(default_factory=list)

class HunyuanImageHuggingfaceImageGenerationModelComponentConfig(CommonHuggingfaceImageGenerationModelComponentConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE]
    actions: List[HunyuanImageHuggingfaceImageGenerationModelActionConfig] = Field(default_factory=list)

HuggingfaceImageGenerationModelComponentConfig = Annotated[
    Union[
        SdxlHuggingfaceImageGenerationModelComponentConfig,
        FluxHuggingfaceImageGenerationModelComponentConfig,
        HunyuanImageHuggingfaceImageGenerationModelComponentConfig,
    ],
    Field(discriminator="architecture")
]
