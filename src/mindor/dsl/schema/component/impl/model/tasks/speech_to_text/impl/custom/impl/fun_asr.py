from typing import Literal, List, Dict, Optional, Union, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import FunAsrSpeechToTextModelActionConfig
from ...common import CommonSpeechToTextModelComponentConfig
from .common import SpeechToTextModelFamily
from .....common import ModelDriver, ModelConfig

_DEFAULT_REPOSITORY         = "FunAudioLLM/Fun-ASR-MLT-Nano-2512"
_DEFAULT_VAD_MODEL          = "fsmn-vad"
_DEFAULT_PUNCTUATION_MODEL  = "ct-punc"

class FunAsrVoiceActivityDetectionConfig(BaseModel):
    model: str = Field(default=_DEFAULT_VAD_MODEL, description="VAD model identifier recognized by FunASR (e.g., fsmn-vad).")
    max_single_segment_time: Optional[Union[str, int, float]] = Field(default=None, description="Maximum length of a single VAD segment, as a duration string (e.g., \"30s\") or seconds.")

class FunAsrPunctuationConfig(BaseModel):
    model: str = Field(default=_DEFAULT_PUNCTUATION_MODEL, description="Punctuation model identifier recognized by FunASR (e.g., ct-punc).")

class FunAsrSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechToTextModelFamily.FUN_ASR]
    model: ModelConfig = Field(..., description="Model identifier — a HuggingFace repo ID or a local path.")
    inverse_text_normalization: bool = Field(default=True, description="Whether to convert spoken forms to written forms (e.g., \"twenty five\" -> \"25\").")
    voice_activity_detection: Optional[FunAsrVoiceActivityDetectionConfig] = Field(default=None, description="Voice activity detection settings; pass `true` to enable with defaults.")
    punctuation: Optional[FunAsrPunctuationConfig] = Field(default=None, description="Punctuation and sentence-splitting model that enables per-sentence timestamps; pass `true` to enable with defaults.")
    actions: List[FunAsrSpeechToTextModelActionConfig] = Field(default_factory=list, description="Actions this speech-to-text component exposes to workflows.")

    @model_validator(mode="before")
    def apply_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = _DEFAULT_REPOSITORY
        return values

    @model_validator(mode="before")
    def inflate_voice_activity_detection(cls, values: Dict[str, Any]):
        vad = values.get("voice_activity_detection")
        if isinstance(vad, bool):
            values["voice_activity_detection"] = {} if vad else None
        return values

    @model_validator(mode="before")
    def inflate_punctuation(cls, values: Dict[str, Any]):
        punctuation = values.get("punctuation")
        if isinstance(punctuation, bool):
            values["punctuation"] = {} if punctuation else None
        return values
