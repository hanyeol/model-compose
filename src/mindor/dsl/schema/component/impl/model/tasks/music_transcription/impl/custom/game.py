from typing import Literal, Optional, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import GameMusicTranscriptionModelActionConfig
from ..common import CommonMusicTranscriptionModelComponentConfig
from .common import MusicTranscriptionModelFamily
from ....common import ModelDriverType, ModelProvider, NamedModelConfig

_DEFAULT_MODEL = "medium"

class GameMusicTranscriptionModelComponentConfig(CommonMusicTranscriptionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicTranscriptionModelFamily.GAME]
    model: NamedModelConfig = Field(..., description="GAME bundle size: 'small', 'medium', or 'large'; downloaded from the openvpi/GAME release on first use.")
    providers: Optional[List[str]] = Field(default=None, description="onnxruntime execution providers; auto-selected from device when omitted.")
    actions: List[GameMusicTranscriptionModelActionConfig] = Field(default_factory=list, description="Actions this music transcription component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str) or model is None:
            values["model"] = { "provider": ModelProvider.NAMED, "name": model or _DEFAULT_MODEL }
        return values
