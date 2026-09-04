from typing import Literal, List, Dict, Any, Optional
from pydantic import Field, model_validator
from mindor.dsl.schema.action import PianoTranscriptionMusicTranscriptionModelActionConfig
from ...common import CommonMusicTranscriptionModelComponentConfig
from .common import MusicTranscriptionModelFamily
from .....common import ModelDriver, ModelProvider, NamedModelConfig

_DEFAULT_MODEL = "note_F1=0.9677_pedal_F1=0.9186.pth"

class PianoTranscriptionMusicTranscriptionModelComponentConfig(CommonMusicTranscriptionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicTranscriptionModelFamily.PIANO_TRANSCRIPTION]
    model: NamedModelConfig = Field(..., description="ByteDance Piano Transcription checkpoint name; downloaded on first use.")
    actions: List[PianoTranscriptionMusicTranscriptionModelActionConfig] = Field(default_factory=list, description="Actions this music transcription component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str) or model is None:
            values["model"] = { "provider": ModelProvider.NAMED, "name": model or _DEFAULT_MODEL }
        return values
