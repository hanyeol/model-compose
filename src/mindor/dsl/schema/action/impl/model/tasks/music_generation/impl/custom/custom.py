from typing import Union
from .ace_step import AceStepMusicGenerationModelActionConfig
from .midi_ddsp import MidiDdspMusicGenerationModelActionConfig
from .yue2 import Yue2MusicGenerationModelActionConfig
from .minimax_music3 import MinimaxMusic3MusicGenerationModelActionConfig

CustomMusicGenerationModelActionConfig = Union[
    AceStepMusicGenerationModelActionConfig,
    MidiDdspMusicGenerationModelActionConfig,
    Yue2MusicGenerationModelActionConfig,
    MinimaxMusic3MusicGenerationModelActionConfig,
]
