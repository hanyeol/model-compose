from typing import Literal, Optional
from enum import Enum
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType, ModelDriver

class MusicGenerationModelFamily(str, Enum):
    ACE_STEP = "ace-step"

class CommonMusicGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MUSIC_GENERATION]
    driver: ModelDriver = Field(default=ModelDriver.CUSTOM)
    family: MusicGenerationModelFamily = Field(..., description="Model family.")
