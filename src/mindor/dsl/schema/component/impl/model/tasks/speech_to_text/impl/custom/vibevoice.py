from typing import Literal, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import VibeVoiceSpeechToTextModelActionConfig
from ..common import CommonSpeechToTextModelComponentConfig
from .common import SpeechToTextModelFamily
from ....common import ModelDriver, ModelConfig

_DEFAULT_REPOSITORY = "microsoft/VibeVoice-ASR-Streaming-1.5B"

class VibeVoiceSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechToTextModelFamily.VIBEVOICE]
    model: ModelConfig = Field(..., description="Model identifier — a HuggingFace repo ID or a local path; must be a VibeVoice ASR streaming checkpoint.")
    compute_type: str = Field(default="auto", description="Numeric precision used for inference (e.g., bfloat16, float16, float32).")
    attn_implementation: Literal[ "sdpa", "flash_attention_2", "eager" ] = Field(default="sdpa", description="Attention kernel used by the underlying transformer.")
    actions: List[VibeVoiceSpeechToTextModelActionConfig] = Field(default_factory=list, description="Actions this speech-to-text component exposes to workflows.")

    @model_validator(mode="before")
    def apply_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = _DEFAULT_REPOSITORY
        return values
