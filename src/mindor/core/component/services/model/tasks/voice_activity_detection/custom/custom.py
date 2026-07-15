from mindor.dsl.schema.component import ModelComponentConfig, VoiceActivityDetectionModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.VOICE_ACTIVITY_DETECTION, ModelDriver.CUSTOM)
class CustomVoiceActivityDetectionTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == VoiceActivityDetectionModelFamily.SILERO:
            from .silero import SileroVoiceActivityDetectionTaskService
            return SileroVoiceActivityDetectionTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
