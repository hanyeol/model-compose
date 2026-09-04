from mindor.dsl.schema.component import ModelComponentConfig, MusicTranscriptionModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.MUSIC_TRANSCRIPTION, ModelDriver.CUSTOM)
class CustomMusicTranscriptionTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicTranscriptionModelFamily.BASIC_PITCH:
            from .basic_pitch import BasicPitchMusicTranscriptionTaskService
            return BasicPitchMusicTranscriptionTaskService(id, config, daemon)

        if config.family == MusicTranscriptionModelFamily.PIANO_TRANSCRIPTION:
            from .piano_transcription import PianoTranscriptionMusicTranscriptionTaskService
            return PianoTranscriptionMusicTranscriptionTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
