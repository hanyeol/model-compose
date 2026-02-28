from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FluxImageGenerationModelActionConfig
from .common import CommonImageGenerationModelComponentConfig, ImageGenerationModelFamily

class FluxImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    family: Literal[ImageGenerationModelFamily.FLUX]
    actions: List[FluxImageGenerationModelActionConfig] = Field(default_factory=list)
