from typing import Literal, Union, List, Annotated, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import Wav2LipLipSyncModelActionConfig
from ..common import CommonLipSyncModelComponentConfig
from .common import LipSyncModelFamily
from ....common import ModelDriverType, ModelProvider, HuggingfaceModelConfig, LocalModelConfig

class Wav2LipPreset(str, Enum):
    WAV2LIP     = "wav2lip"
    WAV2LIP_GAN = "wav2lip-gan"

# Wav2Lip has no first-party HuggingFace repo; the Easy-Wav2Lip release mirror
# hosts both preset checkpoints under stable URLs. Users can still override
# `model` explicitly to point at a private mirror or a pre-downloaded file.
_WAV2LIP_RELEASE_BASEURL = "https://github.com/anothermartz/Easy-Wav2Lip/releases/download/Prerequesits"
_DEFAULT_MODEL_URLS: Dict[Wav2LipPreset, str] = {
    Wav2LipPreset.WAV2LIP:     f"{_WAV2LIP_RELEASE_BASEURL}/Wav2Lip.pth",
    Wav2LipPreset.WAV2LIP_GAN: f"{_WAV2LIP_RELEASE_BASEURL}/Wav2Lip_GAN.pth",
}

class Wav2LipLocalModelConfig(LocalModelConfig):
    def _cache_subdir(self) -> str:
        return "wav2lip"

Wav2LipLipSyncModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        Wav2LipLocalModelConfig,
    ],
    Field(discriminator="provider")
]

class Wav2LipLipSyncModelComponentConfig(CommonLipSyncModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[LipSyncModelFamily.WAV2LIP]
    preset: Wav2LipPreset = Field(default=Wav2LipPreset.WAV2LIP_GAN, description="Wav2Lip checkpoint variant to load.")
    model: Wav2LipLipSyncModelConfig = Field(..., description="Wav2Lip generator checkpoint — a local path or a HuggingFace repo ID.")
    actions: List[Wav2LipLipSyncModelActionConfig] = Field(default_factory=list, description="Actions this lip-sync component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model_from_preset(cls, values: Dict[str, Any]):
        # Fill in a default `model` config that fetches the preset's checkpoint
        # from the Easy-Wav2Lip release mirror when the user hasn't provided one.
        # `LocalModelConfig.apply_default_path` then derives the on-disk path
        # from the URL's basename under `~/.cache/models/wav2lip/`.
        if values.get("model") is None:
            preset = Wav2LipPreset(values.get("preset", Wav2LipPreset.WAV2LIP_GAN))
            values["model"] = {
                "provider": ModelProvider.LOCAL,
                "url": _DEFAULT_MODEL_URLS[preset],
            }
        return values
