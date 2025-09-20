from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Type, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import SwinIRImageUpscaleModelActionConfig
from .common import CommonImageUpscaleModelComponentConfig, ImageUpscaleModelArchitecture

class SwinIRImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    architecture: Literal[ImageUpscaleModelArchitecture.SWINIR]
    actions: List[SwinIRImageUpscaleModelActionConfig] = Field(default_factory=list)

    @classmethod
    def _get_action_class(cls) -> Type[BaseModel]:
        return SwinIRImageUpscaleModelActionConfig
