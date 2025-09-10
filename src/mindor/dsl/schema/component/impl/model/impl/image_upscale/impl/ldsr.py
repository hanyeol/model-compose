from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Type, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import LdsrImageUpscaleModelActionConfig
from .common import CommonImageUpscaleModelComponentConfig, ImageUpscaleModelArchitecture

class LdsrImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    architecture: Literal[ImageUpscaleModelArchitecture.LDSR]
    actions: List[LdsrImageUpscaleModelActionConfig] = Field(default_factory=list)

    @classmethod
    def _get_action_class(cls) -> Type[BaseModel]:
        return LdsrImageUpscaleModelActionConfig
