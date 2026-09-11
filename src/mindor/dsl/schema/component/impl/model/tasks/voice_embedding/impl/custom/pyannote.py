from typing import Literal, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import VoiceEmbeddingModelActionConfig
from ..common import CommonVoiceEmbeddingModelComponentConfig
from .common import VoiceEmbeddingModelFamily
from ....common import ModelDriver, ModelConfig

_DEFAULT_REPOSITORY = "pyannote/embedding"

class PyannoteVoiceEmbeddingModelComponentConfig(CommonVoiceEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[VoiceEmbeddingModelFamily.PYANNOTE]
    model: ModelConfig = Field(..., description="Pyannote embedding model identifier — a HuggingFace repo ID or a local path.")
    actions: List[VoiceEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this voice embedding component exposes to workflows.")

    @model_validator(mode="before")
    def apply_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = _DEFAULT_REPOSITORY
        return values
