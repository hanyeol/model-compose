from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import YoloPoseDetectionModelActionConfig
from ...common import CommonPoseDetectionModelComponentConfig
from .common import PoseDetectionModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt"

class YoloPoseDetectionLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "ultralytics"

YoloPoseDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        YoloPoseDetectionLocalModelConfig
    ],
    Field(discriminator="provider")
]

class YoloPoseDetectionModelComponentConfig(CommonPoseDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[PoseDetectionModelFamily.YOLO]
    model: YoloPoseDetectionModelConfig = Field(..., description="Model repository or local file path.")
    actions: List[YoloPoseDetectionModelActionConfig] = Field(default_factory=list)
