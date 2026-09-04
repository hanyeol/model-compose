from typing import Union, Annotated
from pydantic import Field
from .faster_whisper import FasterWhisperSpeechToTextModelComponentConfig
from .fun_asr import FunAsrSpeechToTextModelComponentConfig
from .crisper_whisper import CrisperWhisperSpeechToTextModelComponentConfig
from .vibevoice import VibeVoiceSpeechToTextModelComponentConfig

CustomSpeechToTextModelComponentConfig = Annotated[
    Union[
        FasterWhisperSpeechToTextModelComponentConfig,
        FunAsrSpeechToTextModelComponentConfig,
        CrisperWhisperSpeechToTextModelComponentConfig,
        VibeVoiceSpeechToTextModelComponentConfig,
    ],
    Field(discriminator="family")
]
