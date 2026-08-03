from typing import Literal, Union, List, Annotated
from pydantic import Field
from mindor.dsl.schema.action import SamImageSegmentationModelActionConfig
from ...common import CommonImageSegmentationModelComponentConfig
from .common import ImageSegmentationModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

class SamImageSegmentationLocalModelConfig(LocalModelConfig):
    def _cache_subdir(self) -> str:
        return "ultralytics"

SamImageSegmentationModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        SamImageSegmentationLocalModelConfig
    ],
    Field(discriminator="provider")
]

class SamImageSegmentationModelComponentConfig(CommonImageSegmentationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ImageSegmentationModelFamily.SAM]
    model: SamImageSegmentationModelConfig = Field(..., description="Model repository or local file path.")
    actions: List[SamImageSegmentationModelActionConfig] = Field(default_factory=list)
