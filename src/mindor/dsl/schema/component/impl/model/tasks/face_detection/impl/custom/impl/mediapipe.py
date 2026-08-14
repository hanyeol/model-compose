from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import BlazeFaceFaceDetectionModelActionConfig
from ...common import CommonFaceDetectionModelComponentConfig
from .common import FaceDetectionModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"

class BlazeFaceFaceDetectionLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "mediapipe"

BlazeFaceFaceDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        BlazeFaceFaceDetectionLocalModelConfig
    ],
    Field(discriminator="provider")
]

class BlazeFaceFaceDetectionModelComponentConfig(CommonFaceDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceDetectionModelFamily.BLAZEFACE]
    model: BlazeFaceFaceDetectionModelConfig = Field(..., description="BlazeFace detector task file identifier — a HuggingFace repo ID or a local path.")
    actions: List[BlazeFaceFaceDetectionModelActionConfig] = Field(default_factory=list, description="Actions this face detection component exposes to workflows.")
