from mindor.dsl.schema.component import ModelComponentConfig, SpeakerDiarizationModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.SPEAKER_DIARIZATION, ModelDriver.CUSTOM)
class CustomSpeakerDiarizationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == SpeakerDiarizationModelFamily.PYANNOTE:
            from .pyannote import PyannoteSpeakerDiarizationTaskService
            return PyannoteSpeakerDiarizationTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
