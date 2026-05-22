from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig, MusicGenerationModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.MUSIC_GENERATION, ModelDriver.CUSTOM)
class CustomMusicGenerationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicGenerationModelFamily.ACE_STEP:
            from .families.ace_step import AceStepMusicGenerationTaskService
            return AceStepMusicGenerationTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
