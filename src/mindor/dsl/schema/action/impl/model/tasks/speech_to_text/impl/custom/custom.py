from typing import Union
from .faster_whisper import FasterWhisperSpeechToTextModelActionConfig
from .fun_asr import FunAsrSpeechToTextModelActionConfig
from .crisper_whisper import CrisperWhisperSpeechToTextModelActionConfig
from .vibevoice import VibeVoiceSpeechToTextModelActionConfig

CustomSpeechToTextModelActionConfig = Union[
    FasterWhisperSpeechToTextModelActionConfig,
    FunAsrSpeechToTextModelActionConfig,
    CrisperWhisperSpeechToTextModelActionConfig,
    VibeVoiceSpeechToTextModelActionConfig,
]
