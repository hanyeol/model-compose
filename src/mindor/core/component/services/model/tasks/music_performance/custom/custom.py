from mindor.dsl.schema.component import ModelComponentConfig, MusicPerformanceModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.MUSIC_PERFORMANCE, ModelDriverType.CUSTOM)
class CustomMusicPerformanceTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicPerformanceModelFamily.VIRTUOSO_NET:
            from .virtuoso_net import VirtuosoNetMusicPerformanceTaskDriver
            return VirtuosoNetMusicPerformanceTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
