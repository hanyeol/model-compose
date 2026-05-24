from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FluxImageGenerationModelActionConfig
from ..common import CommonImageGenerationModelComponentConfig
from ....common import ModelDriver
from .custom import CustomImageGenerationModelFamily

class FluxImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[CustomImageGenerationModelFamily.FLUX]
    actions: List[FluxImageGenerationModelActionConfig] = Field(default_factory=list)
