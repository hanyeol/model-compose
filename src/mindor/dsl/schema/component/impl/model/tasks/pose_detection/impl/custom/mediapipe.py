from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import BlazePosePoseDetectionModelActionConfig
from ..common import CommonPoseDetectionModelComponentConfig
from .common import PoseDetectionModelFamily
from ....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"

class BlazePosePoseDetectionLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "mediapipe"

BlazePosePoseDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        BlazePosePoseDetectionLocalModelConfig
    ],
    Field(discriminator="provider")
]

class BlazePosePoseDetectionModelComponentConfig(CommonPoseDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[PoseDetectionModelFamily.BLAZEPOSE]
    model: BlazePosePoseDetectionModelConfig = Field(..., description="BlazePose landmarker task file identifier — a HuggingFace repo ID or a local path.")
    actions: List[BlazePosePoseDetectionModelActionConfig] = Field(default_factory=list, description="Actions this pose detection component exposes to workflows.")
