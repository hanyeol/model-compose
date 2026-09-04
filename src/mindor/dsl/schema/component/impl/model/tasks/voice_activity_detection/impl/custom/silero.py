from typing import Literal, List, Optional, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import VoiceActivityDetectionModelActionConfig
from ..common import CommonVoiceActivityDetectionModelComponentConfig
from .common import VoiceActivityDetectionModelFamily
from ....common import ModelDriver, ModelConfig

class SileroVoiceActivityDetectionModelComponentConfig(CommonVoiceActivityDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[VoiceActivityDetectionModelFamily.SILERO]
    model: Optional[ModelConfig] = Field(default=None, description="Not configurable; the model ships bundled with the silero-vad package.")
    actions: List[VoiceActivityDetectionModelActionConfig] = Field(default_factory=list, description="Actions this voice activity detection component exposes to workflows.")

    @model_validator(mode="before")
    def reject_model_override(cls, values: Dict[str, Any]):
        if values.get("model") is not None:
            raise ValueError("Silero VAD ships its own model; the 'model' field is not configurable.")
        return values
