from mindor.dsl.schema.component import ModelComponentConfig, CustomTextToSpeechModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.TEXT_TO_SPEECH, ModelDriver.CUSTOM)
class CustomTextToSpeechTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == CustomTextToSpeechModelFamily.QWEN:
            from .qwen import QwenTextToSpeechTaskService
            return QwenTextToSpeechTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
