from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import YoloFaceTrackingModelActionConfig
from ..common import CommonFaceTrackingModelComponentConfig
from .common import FaceTrackingModelFamily
from ....common import ModelDriverType, HuggingfaceModelConfig, LocalModelConfig, ModelPrecision

_DEFAULT_MODEL_URL = "https://huggingface.co/Bingsu/adetailer/resolve/main/face_yolov8n.pt"

class YoloFaceTrackingLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "yolo"

YoloFaceTrackingModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        YoloFaceTrackingLocalModelConfig
    ],
    Field(discriminator="provider")
]

class YoloFaceTrackingModelComponentConfig(CommonFaceTrackingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[FaceTrackingModelFamily.YOLO]
    model: YoloFaceTrackingModelConfig = Field(..., description="YOLO face detector weights identifier — a HuggingFace repo ID or a local .pt path.")
    actions: List[YoloFaceTrackingModelActionConfig] = Field(default_factory=list, description="Actions this face tracking component exposes to workflows.")

    @classmethod
    def is_supported_precision(cls, precision: ModelPrecision) -> bool:
        # Ultralytics `track(half=True)` only accepts fp16; bfloat16 and fp8 are not wired in.
        return precision in (ModelPrecision.FLOAT32, ModelPrecision.FLOAT16)
