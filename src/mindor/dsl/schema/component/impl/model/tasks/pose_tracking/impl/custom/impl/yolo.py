from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import YoloPoseTrackingModelActionConfig
from ...common import CommonPoseTrackingModelComponentConfig
from .common import PoseTrackingModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt"

class YoloPoseTrackingLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "ultralytics"

YoloPoseTrackingModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        YoloPoseTrackingLocalModelConfig
    ],
    Field(discriminator="provider")
]

class YoloPoseTrackingModelComponentConfig(CommonPoseTrackingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[PoseTrackingModelFamily.YOLO]
    model: YoloPoseTrackingModelConfig = Field(..., description="YOLO pose model identifier — a HuggingFace repo ID or a local path.")
    actions: List[YoloPoseTrackingModelActionConfig] = Field(default_factory=list, description="Actions this pose tracking component exposes to workflows.")
