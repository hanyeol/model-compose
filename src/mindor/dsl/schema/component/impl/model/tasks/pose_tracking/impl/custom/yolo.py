from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import YoloPoseTrackingModelActionConfig
from ..common import CommonPoseTrackingModelComponentConfig
from .common import PoseTrackingModelFamily
from ....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig
from pathlib import PurePosixPath

_ULTRALYTICS_RELEASE_BASEURL = "https://github.com/ultralytics/assets/releases/download/v8.3.0"
_DEFAULT_MODEL_URLS: Dict[str, str] = {
    "yolov8n-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8n-pose.pt",
    "yolov8s-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8s-pose.pt",
    "yolov8m-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8m-pose.pt",
    "yolov8l-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8l-pose.pt",
    "yolov8x-pose.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8x-pose.pt",
}

class YoloPoseTrackingLocalModelConfig(LocalModelConfig):
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

    @model_validator(mode="before")
    def inflate_local_model(cls, values: Dict[str, Any]):
        if isinstance(values, dict):
            model = values.get("model")
            if isinstance(model, str):
                url = _DEFAULT_MODEL_URLS.get(f"{model}.pt")
                if url:
                    values["model"] = { "provider": "local", "url": url }
        return values
