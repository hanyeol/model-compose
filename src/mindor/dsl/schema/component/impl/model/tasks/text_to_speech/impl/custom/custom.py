from typing import Union, Annotated
from pydantic import Field
from .impl.qwen import QwenTextToSpeechModelComponentConfig
from .impl.kokoro import KokoroTextToSpeechModelComponentConfig
from .impl.chatterbox import ChatterboxTextToSpeechModelComponentConfig
from .impl.luxtts import LuxttsTextToSpeechModelComponentConfig
from .impl.tada import TadaTextToSpeechModelComponentConfig

CustomTextToSpeechModelComponentConfig = Annotated[
    Union[
        QwenTextToSpeechModelComponentConfig,
        KokoroTextToSpeechModelComponentConfig,
        ChatterboxTextToSpeechModelComponentConfig,
        LuxttsTextToSpeechModelComponentConfig,
        TadaTextToSpeechModelComponentConfig,
    ],
    Field(discriminator="family")
]
