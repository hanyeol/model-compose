from typing import Union, Annotated
from pydantic import Field
from .impl.faster_whisper import FasterWhisperSpeechToTextModelComponentConfig
from .impl.fun_asr import FunAsrSpeechToTextModelComponentConfig

CustomSpeechToTextModelComponentConfig = Annotated[
    Union[
        FasterWhisperSpeechToTextModelComponentConfig,
        FunAsrSpeechToTextModelComponentConfig,
    ],
    Field(discriminator="family")
]
