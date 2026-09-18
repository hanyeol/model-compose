from mindor.dsl.schema.component import ModelComponentConfig, SpeakerDiarizationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.SPEAKER_DIARIZATION, ModelDriverType.CUSTOM)
class CustomSpeakerDiarizationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == SpeakerDiarizationModelFamily.PYANNOTE:
            from .pyannote import PyannoteSpeakerDiarizationTaskDriver
            return PyannoteSpeakerDiarizationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
