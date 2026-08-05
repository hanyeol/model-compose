from typing import Literal, List, Dict, Optional, Union, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import FunAsrSpeechToTextModelActionConfig
from ...common import CommonSpeechToTextModelComponentConfig
from .common import SpeechToTextModelFamily
from .....common import ModelDriver, ModelConfig

_DEFAULT_FUN_ASR_REPOSITORY = "FunAudioLLM/Fun-ASR-MLT-Nano-2512"
_DEFAULT_FUN_ASR_VAD_MODEL  = "fsmn-vad"

class FunAsrVadConfig(BaseModel):
    model: str = Field(default=_DEFAULT_FUN_ASR_VAD_MODEL, description="VAD model identifier passed to FunASR (e.g. 'fsmn-vad').")
    max_single_segment_time: Optional[Union[str, int, float]] = Field(default=None, description="Maximum length of a single VAD segment (e.g. '30s', '500ms', or seconds). FunASR default is 60s.")

class FunAsrSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechToTextModelFamily.FUN_ASR]
    model: ModelConfig = Field(..., description="Model repository or local file path.")
    inverse_text_normalization: bool = Field(default=True, description="Convert spoken forms to written forms (e.g. 'twenty five' → '25').")
    vad: Optional[FunAsrVadConfig] = Field(default=None, description="Voice activity detection settings. Enables sentence-level segmentation with real timestamps.")
    actions: List[FunAsrSpeechToTextModelActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def apply_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = _DEFAULT_FUN_ASR_REPOSITORY
        return values
