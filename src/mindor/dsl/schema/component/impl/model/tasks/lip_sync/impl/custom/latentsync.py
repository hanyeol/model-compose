from typing import Literal, Union, List, Annotated, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import LatentSyncLipSyncModelActionConfig
from ..common import CommonLipSyncModelComponentConfig
from .common import LipSyncModelFamily
from ....common import ModelDriver, ModelProvider, HuggingfaceModelConfig, LocalModelConfig

class LatentSyncPreset(str, Enum):
    V15 = "1.5"
    V16 = "1.6"

# ByteDance ships each release as its own HuggingFace repo. v1.6 renders at
# 512×512, v1.5 at 256×256. Both contain the LatentSync UNet checkpoint
# (`latentsync_unet.pt`) plus a whisper subdir with `tiny.pt`.
_DEFAULT_MODEL_REPOS: Dict[LatentSyncPreset, str] = {
    LatentSyncPreset.V15: "ByteDance/LatentSync-1.5",
    LatentSyncPreset.V16: "ByteDance/LatentSync-1.6",
}

LatentSyncLipSyncModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class LatentSyncLipSyncModelComponentConfig(CommonLipSyncModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[LipSyncModelFamily.LATENTSYNC]
    preset: LatentSyncPreset = Field(default=LatentSyncPreset.V16, description="LatentSync release: 1.5 (256×256) or 1.6 (512×512).")
    model: LatentSyncLipSyncModelConfig = Field(..., description="LatentSync UNet checkpoint — a HuggingFace repo ID or a local directory.")
    actions: List[LatentSyncLipSyncModelActionConfig] = Field(default_factory=list, description="Actions this lip-sync component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model_from_preset(cls, values: Dict[str, Any]):
        # Fill in a default `model` config that snapshots the preset's HF
        # release when the user hasn't provided one. The InsightFace + LPIPS
        # side checkpoints are handled by the task service since they live
        # under `checkpoints/auxiliary/` outside the main snapshot.
        if values.get("model") is None:
            preset = LatentSyncPreset(values.get("preset", LatentSyncPreset.V16))
            values["model"] = {
                "provider": ModelProvider.HUGGINGFACE,
                "repository": _DEFAULT_MODEL_REPOS[preset],
            }
        return values
