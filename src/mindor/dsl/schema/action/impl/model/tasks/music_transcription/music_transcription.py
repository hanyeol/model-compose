from typing import Union
from .impl import *

MusicTranscriptionModelActionConfig = Union[
    BasicPitchMusicTranscriptionModelActionConfig,
    PianoTranscriptionMusicTranscriptionModelActionConfig,
]
