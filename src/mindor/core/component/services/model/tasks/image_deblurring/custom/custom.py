from mindor.dsl.schema.component import ModelComponentConfig, ImageDeblurringModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_DEBLURRING, ModelDriverType.CUSTOM)
class CustomImageDeblurringTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageDeblurringModelFamily.HI_DIFF:
            from .hi_diff import HiDiffImageDeblurringTaskDriver
            return HiDiffImageDeblurringTaskDriver(id, config, daemon)

        if config.family == ImageDeblurringModelFamily.MISC_FILTER:
            from .misc_filter import MiscFilterImageDeblurringTaskDriver
            return MiscFilterImageDeblurringTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
