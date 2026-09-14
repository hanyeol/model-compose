from mindor.dsl.schema.component import ModelComponentConfig, LipSyncModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.LIP_SYNC, ModelDriver.CUSTOM)
class CustomLipSyncTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == LipSyncModelFamily.WAV2LIP:
            from .wav2lip import Wav2LipLipSyncTaskService
            return Wav2LipLipSyncTaskService(id, config, daemon)

        if config.family == LipSyncModelFamily.LATENTSYNC:
            from .latentsync import LatentSyncLipSyncTaskService
            return LatentSyncLipSyncTaskService(id, config, daemon)

        if config.family == LipSyncModelFamily.MUSETALK:
            from .musetalk import MuseTalkLipSyncTaskService
            return MuseTalkLipSyncTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
