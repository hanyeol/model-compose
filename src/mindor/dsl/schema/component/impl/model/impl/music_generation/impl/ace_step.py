from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from .common import CommonMusicGenerationModelComponentConfig, MusicGenerationModelFamily

class AceStepMusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    family: Literal[MusicGenerationModelFamily.ACE_STEP]
    preset: str = Field(default="acestep-v15-turbo", description="Model preset (e.g. 'acestep-v15-turbo', 'acestep-v15-base', 'acestep-v15-sft').")
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list)
