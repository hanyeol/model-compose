from mindor.dsl.schema.component import ModelComponentConfig, MusicPitchEstimationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.MUSIC_PITCH_ESTIMATION, ModelDriverType.CUSTOM)
class CustomMusicPitchEstimationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicPitchEstimationModelFamily.PESTO:
            from .pesto.pesto import PestoMusicPitchEstimationTaskDriver
            return PestoMusicPitchEstimationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
