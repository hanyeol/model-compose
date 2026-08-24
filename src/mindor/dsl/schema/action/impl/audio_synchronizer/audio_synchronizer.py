from typing import Union
from .impl import *

AudioSynchronizerActionConfig = Union[
    NativeAudioSynchronizerActionConfig,
    FFmpegAudioSynchronizerActionConfig,
]
