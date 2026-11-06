from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceSpeechToTextModelArchitecture
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.SPEECH_TO_TEXT, ModelDriverType.HUGGINGFACE)
class HuggingfaceSpeechToTextTaskDriver:
    """Architecture dispatcher for the HuggingFace speech-to-text driver.

    The outer registry entry returns this class; `__new__` instantiates the
    per-architecture driver based on `component.architecture`.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.architecture == HuggingfaceSpeechToTextModelArchitecture.AUTO:
            from .architectures.whisper import AutoHuggingfaceSpeechToTextTaskDriver
            return AutoHuggingfaceSpeechToTextTaskDriver(id, config, daemon)

        if config.architecture == HuggingfaceSpeechToTextModelArchitecture.WHISPER:
            from .architectures.whisper import WhisperHuggingfaceSpeechToTextTaskDriver
            return WhisperHuggingfaceSpeechToTextTaskDriver(id, config, daemon)

        if config.architecture == HuggingfaceSpeechToTextModelArchitecture.VOXTRAL:
            from .architectures.voxtral import VoxtralHuggingfaceSpeechToTextTaskDriver
            return VoxtralHuggingfaceSpeechToTextTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown architecture: {config.architecture}")
