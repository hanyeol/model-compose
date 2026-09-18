from mindor.dsl.schema.component import ModelComponentConfig, VoiceActivityDetectionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.VOICE_ACTIVITY_DETECTION, ModelDriverType.CUSTOM)
class CustomVoiceActivityDetectionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == VoiceActivityDetectionModelFamily.SILERO:
            from .silero import SileroVoiceActivityDetectionTaskDriver
            return SileroVoiceActivityDetectionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
