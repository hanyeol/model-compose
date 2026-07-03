from typing import Union, Annotated
from pydantic import Field
from .impl.ace_step import AceStepMusicGenerationModelComponentConfig

CustomMusicGenerationModelComponentConfig = Annotated[
    Union[
        AceStepMusicGenerationModelComponentConfig,
    ],
    Field(discriminator="family")
]
