from typing import Literal, Union, List, Annotated
from pydantic import Field
from mindor.dsl.schema.action import YoloObjectDetectionModelActionConfig
from ...common import CommonObjectDetectionModelComponentConfig
from .common import ObjectDetectionModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

class YoloObjectDetectionLocalModelConfig(LocalModelConfig):
    def _cache_subdir(self) -> str:
        return "ultralytics"

YoloObjectDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        YoloObjectDetectionLocalModelConfig
    ],
    Field(discriminator="provider")
]

class YoloObjectDetectionModelComponentConfig(CommonObjectDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ObjectDetectionModelFamily.YOLO]
    model: YoloObjectDetectionModelConfig = Field(..., description="Model repository or local file path.")
    actions: List[YoloObjectDetectionModelActionConfig] = Field(default_factory=list)
