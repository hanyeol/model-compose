from typing import Literal, Union, List, Annotated, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import InsightfaceFaceTrackingModelActionConfig
from ...common import CommonFaceTrackingModelComponentConfig
from .common import FaceTrackingModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_MODEL_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/antelopev2.zip"

class InsightfaceFaceTrackingLocalModelConfig(LocalModelConfig):
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

InsightfaceFaceTrackingModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        InsightfaceFaceTrackingLocalModelConfig
    ],
    Field(discriminator="provider")
]

class InsightfaceFaceTrackingModelComponentConfig(CommonFaceTrackingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceTrackingModelFamily.INSIGHTFACE]
    model: InsightfaceFaceTrackingModelConfig = Field(..., description="Model repository or local pack path.")
    actions: List[InsightfaceFaceTrackingModelActionConfig] = Field(default_factory=list)
