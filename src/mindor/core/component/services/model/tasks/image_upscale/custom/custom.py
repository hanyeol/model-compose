from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig, CustomImageUpscaleModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_UPSCALE, ModelDriver.CUSTOM)
class CustomImageUpscaleTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == CustomImageUpscaleModelFamily.ESRGAN:
            from .families.esrgan import EsrganImageUpscaleTaskService
            return EsrganImageUpscaleTaskService(id, config, daemon)

        if config.family == CustomImageUpscaleModelFamily.REAL_ESRGAN:
            from .families.real_esrgan import RealEsrganImageUpscaleTaskService
            return RealEsrganImageUpscaleTaskService(id, config, daemon)

        if config.family == CustomImageUpscaleModelFamily.LDSR:
            from .families.ldsr import LdsrImageUpscaleTaskService
            return LdsrImageUpscaleTaskService(id, config, daemon)

        if config.family == CustomImageUpscaleModelFamily.SWINIR:
            from .families.swinir import SwinIRImageUpscaleTaskService
            return SwinIRImageUpscaleTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
