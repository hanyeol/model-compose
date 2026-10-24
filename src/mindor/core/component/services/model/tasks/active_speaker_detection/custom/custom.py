from mindor.dsl.schema.component import ModelComponentConfig, ActiveSpeakerDetectionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.ACTIVE_SPEAKER_DETECTION, ModelDriverType.CUSTOM)
class CustomActiveSpeakerDetectionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ActiveSpeakerDetectionModelFamily.LIGHT_ASD:
            from .light_asd import LightAsdActiveSpeakerDetectionTaskDriver
            return LightAsdActiveSpeakerDetectionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
