from typing import Literal, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import SpeakerDiarizationModelActionConfig
from ...common import CommonSpeakerDiarizationModelComponentConfig
from .common import SpeakerDiarizationModelFamily
from .....common import ModelDriver, ModelConfig

_DEFAULT_PYANNOTE_REPOSITORY = "pyannote/speaker-diarization-3.1"

class PyannoteSpeakerDiarizationModelComponentConfig(CommonSpeakerDiarizationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeakerDiarizationModelFamily.PYANNOTE]
    model: ModelConfig = Field(..., description="Model repository or local file path.")
    actions: List[SpeakerDiarizationModelActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def apply_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = _DEFAULT_PYANNOTE_REPOSITORY
        return values
