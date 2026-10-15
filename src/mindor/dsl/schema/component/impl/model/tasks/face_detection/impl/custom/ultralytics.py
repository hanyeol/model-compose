from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import YoloFaceDetectionModelActionConfig
from ..common import CommonFaceDetectionModelComponentConfig
from .common import FaceDetectionModelFamily
from ....common import ModelDriverType, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://huggingface.co/Bingsu/adetailer/resolve/main/face_yolov8n.pt"

class YoloFaceDetectionLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "yolo"

YoloFaceDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        YoloFaceDetectionLocalModelConfig
    ],
    Field(discriminator="provider")
]

class YoloFaceDetectionModelComponentConfig(CommonFaceDetectionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[FaceDetectionModelFamily.YOLO]
    model: YoloFaceDetectionModelConfig = Field(..., description="YOLO face detector weights identifier — a HuggingFace repo ID or a local .pt path.")
    actions: List[YoloFaceDetectionModelActionConfig] = Field(default_factory=list, description="Actions this face detection component exposes to workflows.")
