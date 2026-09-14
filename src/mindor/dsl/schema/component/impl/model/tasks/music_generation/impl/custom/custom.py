from typing import Union, Annotated
from pydantic import Field
from .ace_step import AceStepMusicGenerationModelComponentConfig
from .midi_ddsp import MidiDdspMusicGenerationModelComponentConfig
from .yue2 import Yue2MusicGenerationModelComponentConfig

CustomMusicGenerationModelComponentConfig = Annotated[
    Union[
        AceStepMusicGenerationModelComponentConfig,
        MidiDdspMusicGenerationModelComponentConfig,
        Yue2MusicGenerationModelComponentConfig,
    ],
    Field(discriminator="family")
]
