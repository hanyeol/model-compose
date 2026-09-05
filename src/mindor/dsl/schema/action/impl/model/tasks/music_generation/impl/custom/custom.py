from typing import Union
from .ace_step import AceStepMusicGenerationModelActionConfig
from .midi_ddsp import MidiDdspMusicGenerationModelActionConfig

CustomMusicGenerationModelActionConfig = Union[
    AceStepMusicGenerationModelActionConfig,
    MidiDdspMusicGenerationModelActionConfig,
]
