from typing import Literal, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import FunAsrSpeechToTextModelActionConfig
from ...common import CommonSpeechToTextModelComponentConfig
from .common import SpeechToTextModelFamily
from .....common import ModelDriver, ModelConfig

_DEFAULT_FUN_ASR_REPOSITORY = "FunAudioLLM/Fun-ASR-MLT-Nano-2512"

class FunAsrSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechToTextModelFamily.FUN_ASR]
    model: ModelConfig = Field(..., description="Model repository or local file path.")
    inverse_text_normalization: bool = Field(default=True, description="Convert spoken forms to written forms (e.g. 'twenty five' → '25').")
    actions: List[FunAsrSpeechToTextModelActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def apply_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = _DEFAULT_FUN_ASR_REPOSITORY
        return values
