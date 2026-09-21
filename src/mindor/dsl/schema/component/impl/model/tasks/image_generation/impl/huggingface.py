from typing import Literal, List, Union, Annotated
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import (
    SdxlHuggingfaceImageGenerationModelActionConfig,
    FluxHuggingfaceImageGenerationModelActionConfig,
    HunyuanImageHuggingfaceImageGenerationModelActionConfig,
    QwenImageHuggingfaceImageGenerationModelActionConfig,
)
from .common import CommonImageGenerationModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceImageGenerationModelArchitecture(str, Enum):
    SDXL          = "sdxl"
    FLUX          = "flux"
    HUNYUAN_IMAGE = "hunyuan-image"
    QWEN_IMAGE    = "qwen-image"

class CommonHuggingfaceImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]

class SdxlHuggingfaceImageGenerationModelComponentConfig(CommonHuggingfaceImageGenerationModelComponentConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.SDXL]
    actions: List[SdxlHuggingfaceImageGenerationModelActionConfig] = Field(default_factory=list, description="Actions this image generation component exposes to workflows.")

class FluxHuggingfaceImageGenerationModelComponentConfig(CommonHuggingfaceImageGenerationModelComponentConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.FLUX]
    actions: List[FluxHuggingfaceImageGenerationModelActionConfig] = Field(default_factory=list, description="Actions this image generation component exposes to workflows.")

class HunyuanImageHuggingfaceImageGenerationModelComponentConfig(CommonHuggingfaceImageGenerationModelComponentConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE]
    actions: List[HunyuanImageHuggingfaceImageGenerationModelActionConfig] = Field(default_factory=list, description="Actions this image generation component exposes to workflows.")

class QwenImageHuggingfaceImageGenerationModelComponentConfig(CommonHuggingfaceImageGenerationModelComponentConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE]
    actions: List[QwenImageHuggingfaceImageGenerationModelActionConfig] = Field(default_factory=list, description="Actions this image generation component exposes to workflows.")

HuggingfaceImageGenerationModelComponentConfig = Annotated[
    Union[
        SdxlHuggingfaceImageGenerationModelComponentConfig,
        FluxHuggingfaceImageGenerationModelComponentConfig,
        HunyuanImageHuggingfaceImageGenerationModelComponentConfig,
        QwenImageHuggingfaceImageGenerationModelComponentConfig,
    ],
    Field(discriminator="architecture")
]
