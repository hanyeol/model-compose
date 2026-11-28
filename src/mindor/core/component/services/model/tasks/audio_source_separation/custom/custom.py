from mindor.dsl.schema.component import ModelComponentConfig, AudioSourceSeparationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.AUDIO_SOURCE_SEPARATION, ModelDriverType.CUSTOM)
class CustomAudioSourceSeparationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == AudioSourceSeparationModelFamily.SAM_AUDIO:
            from .sam_audio import SamAudioAudioSourceSeparationTaskDriver
            return SamAudioAudioSourceSeparationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
