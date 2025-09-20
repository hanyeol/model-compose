from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Type, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import EsrganImageUpscaleModelActionConfig
from .common import CommonImageUpscaleModelComponentConfig, ImageUpscaleModelArchitecture

class EsrganImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    architecture: Literal[ImageUpscaleModelArchitecture.ESRGAN]
    scale: Union[int, str] = Field(default=2, description="Scale factor supported by the model.")
    actions: List[EsrganImageUpscaleModelActionConfig] = Field(default_factory=list)

    @classmethod
    def _get_action_class(cls) -> Type[BaseModel]:
        return EsrganImageUpscaleModelActionConfig
