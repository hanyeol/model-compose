from typing import Union, Annotated
from enum import Enum
from pydantic import Field

class CustomMusicGenerationModelFamily(str, Enum):
    ACE_STEP = "ace-step"

from .ace_step import AceStepMusicGenerationModelComponentConfig

CustomMusicGenerationModelComponentConfig = Annotated[
    Union[
        AceStepMusicGenerationModelComponentConfig,
    ],
    Field(discriminator="family")
]
