from mindor.dsl.schema.component import ModelComponentConfig, MusicBeatTrackingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.MUSIC_BEAT_TRACKING, ModelDriverType.CUSTOM)
class CustomMusicBeatTrackingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicBeatTrackingModelFamily.BEAT_THIS:
            from .beat_this import BeatThisMusicBeatTrackingTaskDriver
            return BeatThisMusicBeatTrackingTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
