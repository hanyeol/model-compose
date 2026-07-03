from typing import Union, Annotated
from pydantic import Field
from .impl.qwen import QwenTextToSpeechModelComponentConfig
from .impl.kokoro import KokoroTextToSpeechModelComponentConfig
from .impl.chatterbox import ChatterboxTextToSpeechModelComponentConfig

CustomTextToSpeechModelComponentConfig = Annotated[
    Union[
        QwenTextToSpeechModelComponentConfig,
        KokoroTextToSpeechModelComponentConfig,
        ChatterboxTextToSpeechModelComponentConfig,
    ],
    Field(discriminator="family")
]
