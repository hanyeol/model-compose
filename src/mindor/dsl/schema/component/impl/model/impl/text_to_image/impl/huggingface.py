from typing import Literal, List, Union, Annotated
from pydantic import Field
from mindor.dsl.schema.action import (
    HuggingfaceTextToImageModelArchitecture,
    SdxlHuggingfaceTextToImageModelActionConfig,
    FluxHuggingfaceTextToImageModelActionConfig,
    HunyuanImageHuggingfaceTextToImageModelActionConfig,
)
from .common import CommonTextToImageModelComponentConfig
from ...common import ModelDriver

class CommonHuggingfaceTextToImageModelComponentConfig(CommonTextToImageModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE] = Field(default=ModelDriver.HUGGINGFACE)

class SdxlHuggingfaceTextToImageModelComponentConfig(CommonHuggingfaceTextToImageModelComponentConfig):
    architecture: Literal[HuggingfaceTextToImageModelArchitecture.SDXL]
    actions: List[SdxlHuggingfaceTextToImageModelActionConfig] = Field(default_factory=list)

class FluxHuggingfaceTextToImageModelComponentConfig(CommonHuggingfaceTextToImageModelComponentConfig):
    architecture: Literal[HuggingfaceTextToImageModelArchitecture.FLUX]
    actions: List[FluxHuggingfaceTextToImageModelActionConfig] = Field(default_factory=list)

class HunyuanImageHuggingfaceTextToImageModelComponentConfig(CommonHuggingfaceTextToImageModelComponentConfig):
    architecture: Literal[HuggingfaceTextToImageModelArchitecture.HUNYUAN_IMAGE]
    actions: List[HunyuanImageHuggingfaceTextToImageModelActionConfig] = Field(default_factory=list)

HuggingfaceTextToImageModelComponentConfig = Annotated[
    Union[
        SdxlHuggingfaceTextToImageModelComponentConfig,
        FluxHuggingfaceTextToImageModelComponentConfig,
        HunyuanImageHuggingfaceTextToImageModelComponentConfig,
    ],
    Field(discriminator="architecture")
]
