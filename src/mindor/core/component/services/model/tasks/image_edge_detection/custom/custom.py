from mindor.dsl.schema.component import ModelComponentConfig, ImageEdgeDetectionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_EDGE_DETECTION, ModelDriverType.CUSTOM)
class CustomImageEdgeDetectionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageEdgeDetectionModelFamily.HED:
            from .hed import HedImageEdgeDetectionTaskDriver
            return HedImageEdgeDetectionTaskDriver(id, config, daemon)

        if config.family == ImageEdgeDetectionModelFamily.PIDINET:
            from .pidinet import PidinetImageEdgeDetectionTaskDriver
            return PidinetImageEdgeDetectionTaskDriver(id, config, daemon)

        if config.family == ImageEdgeDetectionModelFamily.LINEART:
            from .lineart import LineartImageEdgeDetectionTaskDriver
            return LineartImageEdgeDetectionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
