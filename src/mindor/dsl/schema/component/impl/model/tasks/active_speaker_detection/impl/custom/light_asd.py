from typing import Literal, Union, List, Annotated, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import LightAsdActiveSpeakerDetectionModelActionConfig
from ..common import CommonActiveSpeakerDetectionModelComponentConfig
from .common import ActiveSpeakerDetectionModelFamily
from ....common import ModelDriverType, ModelProvider, HuggingfaceModelConfig, LocalModelConfig

class LightAsdPreset(str, Enum):
    FINETUNING_TALKSET = "finetuning-talkset"
    PRETRAIN_AVA_CVPR  = "pretrain-ava-cvpr"

# Light-ASD has no first-party HuggingFace repo; the upstream GitHub repo ships
# both preset checkpoints under `weight/*.model` directly on `main`. Users can
# still override `model` explicitly to point at a private mirror or a
# pre-downloaded file.
_LIGHT_ASD_WEIGHT_BASEURL = "https://raw.githubusercontent.com/Junhua-Liao/Light-ASD/main/weight"
_DEFAULT_MODEL_URLS: Dict[LightAsdPreset, str] = {
    LightAsdPreset.FINETUNING_TALKSET: f"{_LIGHT_ASD_WEIGHT_BASEURL}/finetuning_TalkSet.model",
    LightAsdPreset.PRETRAIN_AVA_CVPR:  f"{_LIGHT_ASD_WEIGHT_BASEURL}/pretrain_AVA_CVPR.model",
}

class LightAsdLocalModelConfig(LocalModelConfig):
    def _cache_subdir(self) -> str:
        return "light_asd"

LightAsdActiveSpeakerDetectionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LightAsdLocalModelConfig,
    ],
    Field(discriminator="provider")
]

class LightAsdActiveSpeakerDetectionModelComponentConfig(CommonActiveSpeakerDetectionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ActiveSpeakerDetectionModelFamily.LIGHT_ASD]
    preset: LightAsdPreset = Field(default=LightAsdPreset.FINETUNING_TALKSET, description="Light-ASD checkpoint variant to load.")
    model: LightAsdActiveSpeakerDetectionModelConfig = Field(..., description="Light-ASD checkpoint — a local path or a HuggingFace repo ID.")
    actions: List[LightAsdActiveSpeakerDetectionModelActionConfig] = Field(default_factory=list, description="Actions this active-speaker-detection component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model_from_preset(cls, values: Dict[str, Any]):
        # Fill in a default `model` config that fetches the preset's checkpoint
        # from the upstream Light-ASD GitHub repo when the user hasn't provided
        # one. `LocalModelConfig.apply_default_path` then derives the on-disk
        # path from the URL's basename under `~/.cache/models/light_asd/`.
        if values.get("model") is None:
            preset = LightAsdPreset(values.get("preset", LightAsdPreset.FINETUNING_TALKSET))
            values["model"] = {
                "provider": ModelProvider.LOCAL,
                "url": _DEFAULT_MODEL_URLS[preset],
            }
        return values
