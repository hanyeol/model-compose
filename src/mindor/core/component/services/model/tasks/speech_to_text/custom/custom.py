from mindor.dsl.schema.component import ModelComponentConfig, SpeechToTextModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.SPEECH_TO_TEXT, ModelDriverType.CUSTOM)
class CustomSpeechToTextTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == SpeechToTextModelFamily.FASTER_WHISPER:
            from .faster_whisper import FasterWhisperSpeechToTextTaskDriver
            return FasterWhisperSpeechToTextTaskDriver(id, config, daemon)

        if config.family == SpeechToTextModelFamily.FUN_ASR:
            from .fun_asr import FunAsrSpeechToTextTaskDriver
            return FunAsrSpeechToTextTaskDriver(id, config, daemon)

        if config.family == SpeechToTextModelFamily.CRISPER_WHISPER:
            from .crisper_whisper import CrisperWhisperSpeechToTextTaskDriver
            return CrisperWhisperSpeechToTextTaskDriver(id, config, daemon)

        if config.family == SpeechToTextModelFamily.VIBEVOICE:
            from .vibevoice import VibeVoiceSpeechToTextTaskDriver
            return VibeVoiceSpeechToTextTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
