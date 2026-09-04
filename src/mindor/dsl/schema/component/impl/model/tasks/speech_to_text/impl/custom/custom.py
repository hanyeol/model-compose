from typing import Union, Annotated
from pydantic import Field
from .impl.faster_whisper import FasterWhisperSpeechToTextModelComponentConfig
from .impl.fun_asr import FunAsrSpeechToTextModelComponentConfig
from .impl.crisper_whisper import CrisperWhisperSpeechToTextModelComponentConfig
from .impl.vibevoice import VibeVoiceSpeechToTextModelComponentConfig

CustomSpeechToTextModelComponentConfig = Annotated[
    Union[
        FasterWhisperSpeechToTextModelComponentConfig,
        FunAsrSpeechToTextModelComponentConfig,
        CrisperWhisperSpeechToTextModelComponentConfig,
        VibeVoiceSpeechToTextModelComponentConfig,
    ],
    Field(discriminator="family")
]
