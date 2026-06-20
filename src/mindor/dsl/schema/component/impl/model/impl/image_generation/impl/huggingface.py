from typing import Literal, List, Union, Annotated, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
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
    driver: Literal[ModelDriver.HUGGINGFACE] = Field(default=ModelDriver.HUGGINGFACE)

    @model_validator(mode="before")
    def inject_architecture_into_actions(cls, values: Dict[str, Any]):
        architecture = values.get("architecture")
        if architecture is None:
            return values

        actions = values.get("actions")
        if not actions:
            return values

        for action in actions:
            if isinstance(action, dict) and "architecture" not in action:
                action["architecture"] = architecture

        return values

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
