from typing import Union, Annotated
from pydantic import Field
from .qwen import QwenTextToSpeechModelComponentConfig
from .kokoro import KokoroTextToSpeechModelComponentConfig
from .chatterbox import ChatterboxTextToSpeechModelComponentConfig
from .luxtts import LuxttsTextToSpeechModelComponentConfig
from .tada import TadaTextToSpeechModelComponentConfig
from .cosyvoice import CosyvoiceTextToSpeechModelComponentConfig

CustomTextToSpeechModelComponentConfig = Annotated[
    Union[
        QwenTextToSpeechModelComponentConfig,
        KokoroTextToSpeechModelComponentConfig,
        ChatterboxTextToSpeechModelComponentConfig,
        LuxttsTextToSpeechModelComponentConfig,
        TadaTextToSpeechModelComponentConfig,
        CosyvoiceTextToSpeechModelComponentConfig,
    ],
    Field(discriminator="family")
]
