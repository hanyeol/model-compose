from typing import Union
from .impl.faster_whisper import FasterWhisperSpeechToTextModelActionConfig
from .impl.fun_asr import FunAsrSpeechToTextModelActionConfig

CustomSpeechToTextModelActionConfig = Union[
    FasterWhisperSpeechToTextModelActionConfig,
    FunAsrSpeechToTextModelActionConfig,
]
