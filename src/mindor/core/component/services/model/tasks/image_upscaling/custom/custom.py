from mindor.dsl.schema.component import ModelComponentConfig, ImageUpscalingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_UPSCALING, ModelDriverType.CUSTOM)
class CustomImageUpscalingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageUpscalingModelFamily.ESRGAN:
            from .esrgan import EsrganImageUpscalingTaskDriver
            return EsrganImageUpscalingTaskDriver(id, config, daemon)

        if config.family == ImageUpscalingModelFamily.REAL_ESRGAN:
            from .real_esrgan import RealEsrganImageUpscalingTaskDriver
            return RealEsrganImageUpscalingTaskDriver(id, config, daemon)

        if config.family == ImageUpscalingModelFamily.LDSR:
            from .ldsr import LdsrImageUpscalingTaskDriver
            return LdsrImageUpscalingTaskDriver(id, config, daemon)

        if config.family == ImageUpscalingModelFamily.SWINIR:
            from .swinir import SwinIRImageUpscalingTaskDriver
            return SwinIRImageUpscalingTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
