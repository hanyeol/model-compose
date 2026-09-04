from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import InsightfaceFaceSwapModelActionConfig
from ..common import CommonFaceSwapModelComponentConfig
from .common import FaceSwapModelFamily
from ....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx"

class InsightfaceFaceSwapLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
        return values

    def _cache_subdir(self) -> str:
        return "insightface"

InsightfaceFaceSwapModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        InsightfaceFaceSwapLocalModelConfig
    ],
    Field(discriminator="provider")
]

class InsightfaceFaceSwapModelComponentConfig(CommonFaceSwapModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceSwapModelFamily.INSIGHTFACE]
    model: InsightfaceFaceSwapModelConfig = Field(..., description="Face swap model identifier — a HuggingFace repo ID or a local path.")
    detector_model: str = Field(default="buffalo_l", description="InsightFace model pack used for face detection and alignment.")
    actions: List[InsightfaceFaceSwapModelActionConfig] = Field(default_factory=list, description="Actions this face swap component exposes to workflows.")
