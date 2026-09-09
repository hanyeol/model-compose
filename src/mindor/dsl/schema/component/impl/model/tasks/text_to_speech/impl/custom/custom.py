from typing import Union, Annotated
from pydantic import Field
from .qwen import QwenTextToSpeechModelComponentConfig
from .kokoro import KokoroTextToSpeechModelComponentConfig
from .chatterbox import ChatterboxTextToSpeechModelComponentConfig
from .luxtts import LuxttsTextToSpeechModelComponentConfig
from .tada import TadaTextToSpeechModelComponentConfig
from .cosyvoice import CosyvoiceTextToSpeechModelComponentConfig
from .fireredtts3 import FireRedTextToSpeechModelComponentConfig

CustomTextToSpeechModelComponentConfig = Annotated[
    Union[
        QwenTextToSpeechModelComponentConfig,
        KokoroTextToSpeechModelComponentConfig,
        ChatterboxTextToSpeechModelComponentConfig,
        LuxttsTextToSpeechModelComponentConfig,
        TadaTextToSpeechModelComponentConfig,
        CosyvoiceTextToSpeechModelComponentConfig,
        FireRedTextToSpeechModelComponentConfig,
    ],
    Field(discriminator="family")
]
