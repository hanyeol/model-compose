from typing import Literal, Union, List, Annotated
from pydantic import Field
from mindor.dsl.schema.action import SamAudioAudioSourceSeparationModelActionConfig
from ..common import CommonAudioSourceSeparationModelComponentConfig
from .common import AudioSourceSeparationModelFamily
from ....common import ModelDriverType, HuggingfaceModelConfig, LocalModelConfig

class SamAudioAudioSourceSeparationLocalModelConfig(LocalModelConfig):
    def _cache_subdir(self) -> str:
        return "sam_audio"

SamAudioAudioSourceSeparationModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        SamAudioAudioSourceSeparationLocalModelConfig,
    ],
    Field(discriminator="provider")
]

class SamAudioAudioSourceSeparationModelComponentConfig(CommonAudioSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[AudioSourceSeparationModelFamily.SAM_AUDIO]
    model: SamAudioAudioSourceSeparationModelConfig = Field(..., description="SAM-Audio checkpoint identifier — a HuggingFace repo ID (e.g., facebook/sam-audio-large) or a local path.")
    actions: List[SamAudioAudioSourceSeparationModelActionConfig] = Field(default_factory=list, description="Actions this audio source separation component exposes to workflows.")
