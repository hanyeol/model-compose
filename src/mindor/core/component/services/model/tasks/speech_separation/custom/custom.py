from mindor.dsl.schema.component import ModelComponentConfig, SpeechSeparationModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.SPEECH_SEPARATION, ModelDriver.CUSTOM)
class CustomSpeechSeparationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == SpeechSeparationModelFamily.SEPFORMER:
            from .sepformer import SepformerSpeechSeparationTaskService
            return SepformerSpeechSeparationTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
