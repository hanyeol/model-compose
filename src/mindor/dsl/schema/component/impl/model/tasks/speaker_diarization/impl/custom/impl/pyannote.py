from typing import Literal, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import SpeakerDiarizationModelActionConfig
from ...common import CommonSpeakerDiarizationModelComponentConfig
from .common import SpeakerDiarizationModelFamily
from .....common import ModelDriver, ModelConfig

_DEFAULT_REPOSITORY = "pyannote/speaker-diarization-3.1"

class PyannoteSpeakerDiarizationModelComponentConfig(CommonSpeakerDiarizationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeakerDiarizationModelFamily.PYANNOTE]
    model: ModelConfig = Field(..., description="Pyannote diarization model identifier — a HuggingFace repo ID or a local path.")
    actions: List[SpeakerDiarizationModelActionConfig] = Field(default_factory=list, description="Actions this speaker diarization component exposes to workflows.")

    @model_validator(mode="before")
    def apply_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = _DEFAULT_REPOSITORY
        return values
