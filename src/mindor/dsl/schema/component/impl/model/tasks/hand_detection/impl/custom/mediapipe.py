from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import BlazeHandHandDetectionModelActionConfig
from ..common import CommonHandDetectionModelComponentConfig
from .common import HandDetectionModelFamily
from ....common import ModelDriverType, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"

class BlazeHandHandDetectionLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "mediapipe"

BlazeHandHandDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        BlazeHandHandDetectionLocalModelConfig
    ],
    Field(discriminator="provider")
]

class BlazeHandHandDetectionModelComponentConfig(CommonHandDetectionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[HandDetectionModelFamily.BLAZEHAND]
    model: BlazeHandHandDetectionModelConfig = Field(..., description="BlazeHand landmarker task file identifier — a HuggingFace repo ID or a local path.")
    actions: List[BlazeHandHandDetectionModelActionConfig] = Field(default_factory=list, description="Actions this hand detection component exposes to workflows.")
