from typing import Union
from .qwen import QwenTextToSpeechModelActionConfig
from .kokoro import KokoroTextToSpeechModelActionConfig
from .chatterbox import ChatterboxTextToSpeechModelActionConfig
from .luxtts import LuxttsTextToSpeechModelActionConfig
from .tada import TadaTextToSpeechModelActionConfig
from .cosyvoice import CosyvoiceTextToSpeechModelActionConfig

CustomTextToSpeechModelActionConfig = Union[
    QwenTextToSpeechModelActionConfig,
    KokoroTextToSpeechModelActionConfig,
    ChatterboxTextToSpeechModelActionConfig,
    LuxttsTextToSpeechModelActionConfig,
    TadaTextToSpeechModelActionConfig,
    CosyvoiceTextToSpeechModelActionConfig,
]
