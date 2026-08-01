from mindor.dsl.schema.component import ModelComponentConfig, MusicSourceSeparationModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.MUSIC_SOURCE_SEPARATION, ModelDriver.CUSTOM)
class CustomMusicSourceSeparationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicSourceSeparationModelFamily.DEMUCS:
            from .demucs import DemucsMusicSourceSeparationTaskService
            return DemucsMusicSourceSeparationTaskService(id, config, daemon)

        if config.family == MusicSourceSeparationModelFamily.MDX_NET:
            from .mdx_net import MdxNetMusicSourceSeparationTaskService
            return MdxNetMusicSourceSeparationTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
