from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import YoloPoseDetectionModelActionConfig
from ...common import CommonPoseDetectionModelComponentConfig
from .common import PoseDetectionModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig
from pathlib import PurePosixPath

_ULTRALYTICS_RELEASE_BASEURL = "https://github.com/ultralytics/assets/releases/download/v8.3.0"
_DEFAULT_MODEL_URLS: Dict[str, str] = {
    "yolov8n-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8n-pose.pt",
    "yolov8s-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8s-pose.pt",
    "yolov8m-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8m-pose.pt",
    "yolov8l-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8l-pose.pt",
    "yolov8x-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8x-pose.pt",
}

class YoloPoseDetectionLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            path = values.get("path")
            if isinstance(path, str):
                url = _DEFAULT_MODEL_URLS.get(PurePosixPath(path).name)
                if url:
                    values["url"] = url
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
    model: YoloPoseDetectionModelConfig = Field(..., description="YOLO pose model identifier — a HuggingFace repo ID or a local path.")
    actions: List[YoloPoseDetectionModelActionConfig] = Field(default_factory=list, description="Actions this pose detection component exposes to workflows.")
