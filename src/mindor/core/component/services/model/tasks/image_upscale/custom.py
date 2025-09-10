from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig, ImageUpscaleModelArchitecture
from ...base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_UPSCALE, ModelDriver.CUSTOM)
class CustomImageUpscaleTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.architecture == ImageUpscaleModelArchitecture.ESRGAN:
            from .esrgan import EsrganImageUpscaleTaskService
            return EsrganImageUpscaleTaskService(id, config, daemon)

        if config.architecture == ImageUpscaleModelArchitecture.REAL_ESRGAN:
            from .real_esrgan import RealEsrganImageUpscaleTaskService
            return RealEsrganImageUpscaleTaskService(id, config, daemon)

        if config.architecture == ImageUpscaleModelArchitecture.LDSR:
            from .ldsr import LdsrImageUpscaleTaskService
            return LdsrImageUpscaleTaskService(id, config, daemon)

        if config.architecture == ImageUpscaleModelArchitecture.SWINIR:
            from .swinir import SwinIRImageUpscaleTaskService
            return SwinIRImageUpscaleTaskService(id, config, daemon)

        raise ValueError(f"Unknown architecture: {config.architecture}")
