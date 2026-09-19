from mindor.dsl.schema.component import ModelComponentConfig, ImageTo3DModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_TO_3D, ModelDriverType.CUSTOM)
class CustomImageTo3DTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageTo3DModelFamily.PIXAL3D:
            from .pixal3d import Pixal3DImageTo3DTaskDriver
            return Pixal3DImageTo3DTaskDriver(id, config, daemon)

        if config.family == ImageTo3DModelFamily.ANIGEN:
            from .anigen import AniGenImageTo3DTaskDriver
            return AniGenImageTo3DTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
