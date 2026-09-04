from typing import Literal, List, Dict, Any, Optional
from pydantic import Field, model_validator
from mindor.dsl.schema.action import BasicPitchMusicTranscriptionModelActionConfig
from ...common import CommonMusicTranscriptionModelComponentConfig
from .common import MusicTranscriptionModelFamily
from .....common import ModelDriver, ModelProvider, NamedModelConfig

_DEFAULT_MODEL = "icassp-2022"

class BasicPitchMusicTranscriptionModelComponentConfig(CommonMusicTranscriptionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicTranscriptionModelFamily.BASIC_PITCH]
    model: NamedModelConfig = Field(..., description="Basic Pitch pretrained model name (e.g., icassp-2022).")
    actions: List[BasicPitchMusicTranscriptionModelActionConfig] = Field(default_factory=list, description="Actions this music transcription component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str) or model is None:
            values["model"] = { "provider": ModelProvider.NAMED, "name": model or _DEFAULT_MODEL }
        return values
