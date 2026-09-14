from typing import Union
from .ace_step import AceStepMusicGenerationModelActionConfig
from .midi_ddsp import MidiDdspMusicGenerationModelActionConfig
from .yue2 import Yue2MusicGenerationModelActionConfig

CustomMusicGenerationModelActionConfig = Union[
    AceStepMusicGenerationModelActionConfig,
    MidiDdspMusicGenerationModelActionConfig,
    Yue2MusicGenerationModelActionConfig,
]
