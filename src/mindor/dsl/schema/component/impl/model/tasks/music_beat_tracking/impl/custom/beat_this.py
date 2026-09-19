from typing import Literal, Union, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import BeatThisMusicBeatTrackingModelActionConfig
from ..common import CommonMusicBeatTrackingModelComponentConfig
from .common import MusicBeatTrackingModelFamily
from ....common import ModelDriverType, ModelProvider, NamedModelConfig

_DEFAULT_MODEL = "final0"

class BeatThisMusicBeatTrackingModelComponentConfig(CommonMusicBeatTrackingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicBeatTrackingModelFamily.BEAT_THIS]
    model: NamedModelConfig = Field(..., description="Beat This! checkpoint name (e.g., final0, final1, final2, small0, small1, small2).")
    dbn: Union[bool, str] = Field(default=False, description="Whether to apply madmom DBN post-processing to refine beat and downbeat positions.")
    actions: List[BeatThisMusicBeatTrackingModelActionConfig] = Field(default_factory=list, description="Actions this music beat tracking component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str) or model is None:
            values["model"] = { "provider": ModelProvider.NAMED, "name": model or _DEFAULT_MODEL }
        return values
