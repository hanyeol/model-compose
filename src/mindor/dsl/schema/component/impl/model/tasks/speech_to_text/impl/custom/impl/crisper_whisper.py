from typing import Literal, List, Dict, Optional, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import CrisperWhisperSpeechToTextModelActionConfig
from ...common import CommonSpeechToTextModelComponentConfig
from .common import SpeechToTextModelFamily
from .....common import ModelDriver, ModelConfig

_DEFAULT_MODEL = "large"

class CrisperWhisperSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechToTextModelFamily.CRISPER_WHISPER]
    model: ModelConfig = Field(..., description="Model size shorthand, HuggingFace id, or local path.")
    backend: Literal[ "auto", "ct2", "transformers" ] = Field(default="auto", description="Inference backend.")
    compute_type: str = Field(default="auto", description="Compute type (e.g. 'float16', 'int8', 'float32').")
    draft_model: Optional[str] = Field(default=None, description="Draft model for speculative decoding (ct2 only).")
    actions: List[CrisperWhisperSpeechToTextModelActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def apply_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = _DEFAULT_MODEL
        return values
