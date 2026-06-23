from mindor.dsl.schema.component import ModelComponentConfig, SpeechToTextModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.SPEECH_TO_TEXT, ModelDriver.CUSTOM)
class CustomSpeechToTextTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == SpeechToTextModelFamily.FASTER_WHISPER:
            from .faster_whisper import FasterWhisperSpeechToTextTaskService
            return FasterWhisperSpeechToTextTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
