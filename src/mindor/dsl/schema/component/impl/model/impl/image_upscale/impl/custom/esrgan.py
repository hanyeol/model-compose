from typing import Union, Literal, List
from pydantic import Field
from mindor.dsl.schema.action import EsrganImageUpscaleModelActionConfig
from ..common import CommonImageUpscaleModelComponentConfig
from .custom import CustomImageUpscaleModelFamily
from ....common import ModelDriver

class EsrganImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[CustomImageUpscaleModelFamily.ESRGAN]
    scale: Union[int, str] = Field(default=2, description="Upscaling scale factor.")
    actions: List[EsrganImageUpscaleModelActionConfig] = Field(default_factory=list)
