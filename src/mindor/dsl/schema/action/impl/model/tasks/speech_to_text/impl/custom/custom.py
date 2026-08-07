from typing import Union
from .impl.faster_whisper import FasterWhisperSpeechToTextModelActionConfig
from .impl.fun_asr import FunAsrSpeechToTextModelActionConfig
from .impl.crisper_whisper import CrisperWhisperSpeechToTextModelActionConfig

CustomSpeechToTextModelActionConfig = Union[
    FasterWhisperSpeechToTextModelActionConfig,
    FunAsrSpeechToTextModelActionConfig,
    CrisperWhisperSpeechToTextModelActionConfig,
]
