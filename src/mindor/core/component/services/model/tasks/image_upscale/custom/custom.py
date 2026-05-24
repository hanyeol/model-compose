from mindor.dsl.schema.component import ModelComponentConfig, CustomImageUpscaleModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_UPSCALE, ModelDriver.CUSTOM)
class CustomImageUpscaleTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == CustomImageUpscaleModelFamily.ESRGAN:
            from .esrgan import EsrganImageUpscaleTaskService
            return EsrganImageUpscaleTaskService(id, config, daemon)

        if config.family == CustomImageUpscaleModelFamily.REAL_ESRGAN:
            from .real_esrgan import RealEsrganImageUpscaleTaskService
            return RealEsrganImageUpscaleTaskService(id, config, daemon)

        if config.family == CustomImageUpscaleModelFamily.LDSR:
            from .ldsr import LdsrImageUpscaleTaskService
            return LdsrImageUpscaleTaskService(id, config, daemon)

        if config.family == CustomImageUpscaleModelFamily.SWINIR:
            from .swinir import SwinIRImageUpscaleTaskService
            return SwinIRImageUpscaleTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
