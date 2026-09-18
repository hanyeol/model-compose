from mindor.dsl.schema.component import ModelComponentConfig, TextToSpeechModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.TEXT_TO_SPEECH, ModelDriverType.CUSTOM)
class CustomTextToSpeechTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == TextToSpeechModelFamily.QWEN:
            from .qwen import QwenTextToSpeechTaskDriver
            return QwenTextToSpeechTaskDriver(id, config, daemon)

        if config.family == TextToSpeechModelFamily.KOKORO:
            from .kokoro import KokoroTextToSpeechTaskDriver
            return KokoroTextToSpeechTaskDriver(id, config, daemon)

        if config.family == TextToSpeechModelFamily.CHATTERBOX:
            from .chatterbox import ChatterboxTextToSpeechTaskDriver
            return ChatterboxTextToSpeechTaskDriver(id, config, daemon)

        if config.family == TextToSpeechModelFamily.LUXTTS:
            from .luxtts import LuxttsTextToSpeechTaskDriver
            return LuxttsTextToSpeechTaskDriver(id, config, daemon)

        if config.family == TextToSpeechModelFamily.TADA:
            from .tada import TadaTextToSpeechTaskDriver
            return TadaTextToSpeechTaskDriver(id, config, daemon)

        if config.family == TextToSpeechModelFamily.COSYVOICE:
            from .cosyvoice import CosyvoiceTextToSpeechTaskDriver
            return CosyvoiceTextToSpeechTaskDriver(id, config, daemon)

        if config.family == TextToSpeechModelFamily.FIREREDTTS3:
            from .fireredtts3 import FireRedTextToSpeechTaskDriver
            return FireRedTextToSpeechTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
