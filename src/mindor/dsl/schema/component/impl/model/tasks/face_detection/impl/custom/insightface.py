from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import InsightfaceFaceDetectionModelActionConfig
from ..common import CommonFaceDetectionModelComponentConfig
from .common import FaceDetectionModelFamily
from ....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/antelopev2.zip"

class InsightfaceFaceDetectionLocalModelConfig(LocalModelConfig):
    @model_validator(mode="before")
    def apply_default_url(cls, values: Dict[str, Any]):
        if isinstance(values, dict) and not values.get("url"):
            values["url"] = _DEFAULT_MODEL_URL
            # The antelopev2 pack ships as a .zip that expands into the pack
            # directory, so the provisioner must treat it as a bundled archive.
            values.setdefault("bundled", True)
        return values

    def _cache_subdir(self) -> str:
        return "insightface"

InsightfaceFaceDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        InsightfaceFaceDetectionLocalModelConfig
    ],
    Field(discriminator="provider")
]

class InsightfaceFaceDetectionModelComponentConfig(CommonFaceDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceDetectionModelFamily.INSIGHTFACE]
    model: InsightfaceFaceDetectionModelConfig = Field(..., description="InsightFace detection pack identifier — a HuggingFace repo ID or a local pack path.")
    actions: List[InsightfaceFaceDetectionModelActionConfig] = Field(default_factory=list, description="Actions this face detection component exposes to workflows.")
