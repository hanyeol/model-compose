from typing import Union, Annotated
from pydantic import Field
from .ace_step import AceStepMusicGenerationModelComponentConfig
from .midi_ddsp import MidiDdspMusicGenerationModelComponentConfig

CustomMusicGenerationModelComponentConfig = Annotated[
    Union[
        AceStepMusicGenerationModelComponentConfig,
        MidiDdspMusicGenerationModelComponentConfig,
    ],
    Field(discriminator="family")
]
