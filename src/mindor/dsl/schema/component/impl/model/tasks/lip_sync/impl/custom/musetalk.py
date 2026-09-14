from typing import Literal, Union, List, Annotated, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import MuseTalkLipSyncModelActionConfig
from ..common import CommonLipSyncModelComponentConfig
from .common import LipSyncModelFamily
from ....common import ModelDriver, ModelProvider, HuggingfaceModelConfig, LocalModelConfig

class MuseTalkPreset(str, Enum):
    V1  = "v1"
    V15 = "v15"

# `TMElyralab/MuseTalk` bundles both v1.0 and v1.5 UNet weights side by side
# on HuggingFace. `allow_patterns` filters the snapshot to the preset's own
# subdirectory so a single preset switch doesn't pull the other version's
# checkpoint too.
_MUSETALK_REPO = "TMElyralab/MuseTalk"
_DEFAULT_MODEL_ALLOW_PATTERNS: Dict[MuseTalkPreset, List[str]] = {
    MuseTalkPreset.V1:  [ "musetalk/*" ],
    MuseTalkPreset.V15: [ "musetalkV15/*" ],
}

MuseTalkLipSyncModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class MuseTalkLipSyncModelComponentConfig(CommonLipSyncModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[LipSyncModelFamily.MUSETALK]
    preset: MuseTalkPreset = Field(default=MuseTalkPreset.V15, description="MuseTalk release: v1 (bbox_shift tuning) or v15 (default; parsing-based blending).")
    model: MuseTalkLipSyncModelConfig = Field(..., description="MuseTalk UNet checkpoint — a HuggingFace repo ID or a local directory.")
    actions: List[MuseTalkLipSyncModelActionConfig] = Field(default_factory=list, description="Actions this lip-sync component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model_from_preset(cls, values: Dict[str, Any]):
        # Fill in a default `model` config that snapshots only the preset's
        # subdirectory from `TMElyralab/MuseTalk` when the user hasn't provided
        # one. The extra checkpoints (VAE, whisper, dwpose, face-parsing) are
        # handled by the task service since they live under different repos.
        if values.get("model") is None:
            preset = MuseTalkPreset(values.get("preset", MuseTalkPreset.V15))
            values["model"] = {
                "provider": ModelProvider.HUGGINGFACE,
                "repository": _MUSETALK_REPO,
                "allow_patterns": _DEFAULT_MODEL_ALLOW_PATTERNS[preset],
            }
        return values
