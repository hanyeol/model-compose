from typing import Union, Literal, List
from pydantic import Field
from mindor.dsl.schema.action import RealEsrganImageUpscaleModelActionConfig
from .common import CommonImageUpscaleModelComponentConfig, ImageUpscaleModelFamily

class RealEsrganImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    family: Literal[ImageUpscaleModelFamily.REAL_ESRGAN]
    scale: Union[int, str] = Field(default=2, description="Scale factor supported by the model.")
    actions: List[RealEsrganImageUpscaleModelActionConfig] = Field(default_factory=list)
