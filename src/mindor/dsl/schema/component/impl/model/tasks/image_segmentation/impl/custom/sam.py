from typing import Literal, Union, List, Annotated
from pydantic import Field
from mindor.dsl.schema.action import SamImageSegmentationModelActionConfig
from ..common import CommonImageSegmentationModelComponentConfig
from .common import ImageSegmentationModelFamily
from ....common import ModelDriverType, HuggingfaceModelConfig, LocalModelConfig

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
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageSegmentationModelFamily.SAM]
    model: SamImageSegmentationModelConfig = Field(..., description="SAM checkpoint identifier — a HuggingFace repo ID or a local path.")
    actions: List[SamImageSegmentationModelActionConfig] = Field(default_factory=list, description="Actions this image segmentation component exposes to workflows.")
