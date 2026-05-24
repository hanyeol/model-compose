from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from ..common import CommonMusicGenerationModelComponentConfig
from .custom import CustomMusicGenerationModelFamily
from ....common import ModelDriver

class AceStepMusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[CustomMusicGenerationModelFamily.ACE_STEP]
    preset: str = Field(default="acestep-v15-turbo", description="Model preset (e.g. 'acestep-v15-turbo', 'acestep-v15-base', 'acestep-v15-sft').")
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list)
