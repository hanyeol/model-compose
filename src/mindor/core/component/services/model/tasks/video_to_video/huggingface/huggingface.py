from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceVideoToVideoModelArchitecture
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.VIDEO_TO_VIDEO, ModelDriverType.HUGGINGFACE)
class HuggingfaceVideoToVideoTaskDriver:
    """Architecture dispatcher for the HuggingFace video-to-video driver.

    The outer registry entry returns this class; `__new__` instantiates the
    per-architecture driver based on `component.architecture`.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.architecture == HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF:
            from .architectures.animatediff import AnimateDiffHuggingfaceVideoToVideoTaskDriver
            return AnimateDiffHuggingfaceVideoToVideoTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown architecture: {config.architecture}")
