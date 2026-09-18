from mindor.dsl.schema.component import ModelComponentConfig, ImageUpscaleModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_UPSCALE, ModelDriverType.CUSTOM)
class CustomImageUpscaleTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageUpscaleModelFamily.ESRGAN:
            from .esrgan import EsrganImageUpscaleTaskDriver
            return EsrganImageUpscaleTaskDriver(id, config, daemon)

        if config.family == ImageUpscaleModelFamily.REAL_ESRGAN:
            from .real_esrgan import RealEsrganImageUpscaleTaskDriver
            return RealEsrganImageUpscaleTaskDriver(id, config, daemon)

        if config.family == ImageUpscaleModelFamily.LDSR:
            from .ldsr import LdsrImageUpscaleTaskDriver
            return LdsrImageUpscaleTaskDriver(id, config, daemon)

        if config.family == ImageUpscaleModelFamily.SWINIR:
            from .swinir import SwinIRImageUpscaleTaskDriver
            return SwinIRImageUpscaleTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
