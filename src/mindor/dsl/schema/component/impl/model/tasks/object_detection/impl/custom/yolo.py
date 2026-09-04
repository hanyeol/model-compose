from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import YoloObjectDetectionModelActionConfig
from ..common import CommonObjectDetectionModelComponentConfig
from .common import ObjectDetectionModelFamily
from ....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig
from pathlib import PurePosixPath

_ULTRALYTICS_RELEASE_BASEURL = "https://github.com/ultralytics/assets/releases/download/v8.3.0"
_DEFAULT_MODEL_URLS: Dict[str, str] = {
    "yolov8n.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8n.pt",
    "yolov8s.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8s.pt",
    "yolov8m.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8m.pt",
    "yolov8l.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8l.pt",
    "yolov8x.pt": f"{_ULTRALYTICS_RELEASE_BASEURL}/yolov8x.pt",
}

class YoloObjectDetectionLocalModelConfig(LocalModelConfig):
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
    model: YoloObjectDetectionModelConfig = Field(..., description="YOLO detection model identifier — a HuggingFace repo ID or a local path.")
    actions: List[YoloObjectDetectionModelActionConfig] = Field(default_factory=list, description="Actions this object detection component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_local_model(cls, values: Dict[str, Any]):
        if isinstance(values, dict):
            model = values.get("model")
            if isinstance(model, str):
                url = _DEFAULT_MODEL_URLS.get(f"{model}.pt")
                if url:
                    values["model"] = { "provider": "local", "url": url }
        return values
