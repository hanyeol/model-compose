from typing import Literal, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import MusicSourceSeparationModelActionConfig
from ...common import CommonMusicSourceSeparationModelComponentConfig
from .common import MusicSourceSeparationModelFamily
from .....common import ModelDriver, ModelProvider, NamedModelConfig

_DEFAULT_DEMUCS_MODEL = "htdemucs_ft"

class DemucsMusicSourceSeparationModelComponentConfig(CommonMusicSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicSourceSeparationModelFamily.DEMUCS]
    model: NamedModelConfig = Field(..., description="Demucs pretrained model name (e.g. 'htdemucs_ft', 'htdemucs', 'mdx_extra').")
    actions: List[MusicSourceSeparationModelActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str) or model is None:
            values["model"] = { "provider": ModelProvider.NAMED, "name": model or _DEFAULT_DEMUCS_MODEL }
        return values
