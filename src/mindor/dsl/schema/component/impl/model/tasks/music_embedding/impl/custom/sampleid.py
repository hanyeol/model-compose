from typing import Literal, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import MusicEmbeddingModelActionConfig
from ..common import CommonMusicEmbeddingModelComponentConfig
from .common import MusicEmbeddingModelFamily
from ....common import ModelDriver, ModelProvider, NamedModelConfig

_DEFAULT_MODEL = "sampleid-best"

class SampleidMusicEmbeddingModelComponentConfig(CommonMusicEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicEmbeddingModelFamily.SAMPLEID]
    model: NamedModelConfig = Field(..., description="Sample ID checkpoint name or local .ckpt path; downloaded from Zenodo on first use.")
    actions: List[MusicEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this music embedding component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str) or model is None:
            values["model"] = { "provider": ModelProvider.NAMED, "name": model or _DEFAULT_MODEL }
        return values
