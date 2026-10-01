from typing import Literal, Optional, List, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import RapidOcrImageToTextModelActionConfig
from ..common import CommonImageToTextModelComponentConfig
from .common import ImageToTextModelFamily
from ....common import ModelDriverType, ModelProvider, NamedModelConfig

class RapidOcrModel(str, Enum):
    V6_SMALL  = "v6-small"
    V6_TINY   = "v6-tiny"
    V6_MEDIUM = "v6-medium"
    V5_MOBILE = "v5-mobile"
    V5_SERVER = "v5-server"
    V4_MOBILE = "v4-mobile"
    V4_SERVER = "v4-server"

_DEFAULT_MODEL = RapidOcrModel.V6_SMALL

class RapidOcrImageToTextModelComponentConfig(CommonImageToTextModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageToTextModelFamily.RAPIDOCR]
    model: NamedModelConfig = Field(..., description="RapidOCR preset selecting the PP-OCR version and size (e.g., v6-small, v5-mobile, v4-mobile). See the preset × language matrix in the docs.")
    language: Optional[str] = Field(default=None, description="Recognition language as an ISO 639-1 / BCP 47 code (en, ko, ja, zh-CN, ...). See docs/reference/compose/language-codes.md. Which languages a model preset supports depends on the PP-OCR version it selects.")
    actions: List[RapidOcrImageToTextModelActionConfig] = Field(default_factory=list, description="Actions this image-to-text component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str) or model is None:
            name = model or _DEFAULT_MODEL.value
            if name not in { variant.value for variant in RapidOcrModel }:
                supported = ", ".join(variant.value for variant in RapidOcrModel)
                raise ValueError(f"Unknown RapidOCR model {name!r}. Supported: {supported}.")
            values["model"] = { "provider": ModelProvider.NAMED, "name": name }
        return values
