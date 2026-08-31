from typing import Literal, Union, List, Annotated
from pydantic import Field
from mindor.dsl.schema.action import YoloObjectTrackingModelActionConfig
from ...common import CommonObjectTrackingModelComponentConfig
from .common import ObjectTrackingModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

class YoloObjectTrackingLocalModelConfig(LocalModelConfig):
    def _cache_subdir(self) -> str:
        return "ultralytics"

YoloObjectTrackingModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        YoloObjectTrackingLocalModelConfig
    ],
    Field(discriminator="provider")
]

class YoloObjectTrackingModelComponentConfig(CommonObjectTrackingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ObjectTrackingModelFamily.YOLO]
    model: YoloObjectTrackingModelConfig = Field(..., description="YOLO detection model identifier — a HuggingFace repo ID or a local path.")
    actions: List[YoloObjectTrackingModelActionConfig] = Field(default_factory=list, description="Actions this object tracking component exposes to workflows.")
