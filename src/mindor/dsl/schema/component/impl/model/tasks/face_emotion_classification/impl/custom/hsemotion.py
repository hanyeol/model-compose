from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import HSEmotionFaceEmotionClassificationModelActionConfig
from ..common import CommonFaceEmotionClassificationModelComponentConfig
from .common import FaceEmotionClassificationModelFamily
from ....common import ModelDriverType, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://github.com/av-savchenko/face-emotion-recognition/raw/main/models/affectnet_emotions/onnx/enet_b0_8_best_afew.onnx"

class HSEmotionFaceEmotionClassificationLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "hsemotion"

HSEmotionFaceEmotionClassificationModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        HSEmotionFaceEmotionClassificationLocalModelConfig
    ],
    Field(discriminator="provider")
]

class HSEmotionFaceEmotionClassificationModelComponentConfig(CommonFaceEmotionClassificationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[FaceEmotionClassificationModelFamily.HSEMOTION]
    model: HSEmotionFaceEmotionClassificationModelConfig = Field(..., description="HSEmotion ONNX model identifier — a HuggingFace repo ID or a local .onnx path.")
    actions: List[HSEmotionFaceEmotionClassificationModelActionConfig] = Field(default_factory=list, description="Actions this face emotion classification component exposes to workflows.")
