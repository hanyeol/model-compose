from mindor.dsl.schema.component import ModelComponentConfig, LipSyncModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.LIP_SYNC, ModelDriverType.CUSTOM)
class CustomLipSyncTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == LipSyncModelFamily.WAV2LIP:
            from .wav2lip import Wav2LipLipSyncTaskDriver
            return Wav2LipLipSyncTaskDriver(id, config, daemon)

        if config.family == LipSyncModelFamily.LATENTSYNC:
            from .latentsync import LatentSyncLipSyncTaskDriver
            return LatentSyncLipSyncTaskDriver(id, config, daemon)

        if config.family == LipSyncModelFamily.MUSETALK:
            from .musetalk import MuseTalkLipSyncTaskDriver
            return MuseTalkLipSyncTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
