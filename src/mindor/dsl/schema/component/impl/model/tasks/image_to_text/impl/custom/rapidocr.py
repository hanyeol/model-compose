from typing import Literal, Optional, List, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import RapidOcrImageToTextModelActionConfig
from ..common import CommonImageToTextModelComponentConfig
from .common import ImageToTextModelFamily
from ....common import ModelDriverType, ModelConfig

class RapidOcrPreset(str, Enum):
    V6_SMALL  = "v6-small"
    V6_TINY   = "v6-tiny"
    V6_MEDIUM = "v6-medium"
    V5_MOBILE = "v5-mobile"
    V5_SERVER = "v5-server"
    V4_MOBILE = "v4-mobile"
    V4_SERVER = "v4-server"

class RapidOcrImageToTextModelComponentConfig(CommonImageToTextModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageToTextModelFamily.RAPIDOCR]
    model: Optional[ModelConfig] = Field(default=None, description="Not configurable; the model ships bundled with the rapidocr package.")
    preset: RapidOcrPreset = Field(default=RapidOcrPreset.V6_SMALL, description="RapidOCR model preset selecting the PP-OCR version and size.")
    language: Optional[str] = Field(default=None, description="Recognition language as an ISO 639-1 / BCP 47 code (en, ko, ja, zh-CN, ...). See docs/reference/compose/language-codes.md. Which languages a preset supports depends on the PP-OCR version it selects.")
    actions: List[RapidOcrImageToTextModelActionConfig] = Field(default_factory=list, description="Actions this image-to-text component exposes to workflows.")

    @model_validator(mode="before")
    def reject_model_override(cls, values: Dict[str, Any]):
        if values.get("model") is not None:
            raise ValueError("RapidOCR ships its own model; the 'model' field is not configurable.")
        return values
