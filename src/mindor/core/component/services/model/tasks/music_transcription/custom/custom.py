from mindor.dsl.schema.component import ModelComponentConfig, MusicTranscriptionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.MUSIC_TRANSCRIPTION, ModelDriverType.CUSTOM)
class CustomMusicTranscriptionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicTranscriptionModelFamily.BASIC_PITCH:
            from .basic_pitch import BasicPitchMusicTranscriptionTaskDriver
            return BasicPitchMusicTranscriptionTaskDriver(id, config, daemon)

        if config.family == MusicTranscriptionModelFamily.PIANO_TRANSCRIPTION:
            from .piano_transcription import PianoTranscriptionMusicTranscriptionTaskDriver
            return PianoTranscriptionMusicTranscriptionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
