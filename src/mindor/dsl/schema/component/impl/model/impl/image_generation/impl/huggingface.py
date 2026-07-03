from typing import Literal, List, Union, Annotated
from pydantic import Field
from mindor.dsl.schema.action import (
    HuggingfaceImageGenerationModelArchitecture,
    SdxlHuggingfaceImageGenerationModelActionConfig,
    FluxHuggingfaceImageGenerationModelActionConfig,
    HunyuanImageHuggingfaceImageGenerationModelActionConfig,
)
from .common import CommonImageGenerationModelComponentConfig
from ...common import ModelDriver

class CommonHuggingfaceImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE] = Field(default=ModelDriver.HUGGINGFACE)

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
