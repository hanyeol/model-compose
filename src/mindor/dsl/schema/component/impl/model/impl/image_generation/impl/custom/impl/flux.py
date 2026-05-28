from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FluxImageGenerationModelActionConfig
from ...common import CommonImageGenerationModelComponentConfig
from .....common import ModelDriver
from .common import ImageGenerationModelFamily

class FluxImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ImageGenerationModelFamily.FLUX]
    actions: List[FluxImageGenerationModelActionConfig] = Field(default_factory=list)
