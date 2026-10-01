from mindor.dsl.schema.component import ModelComponentConfig, HuggingfaceImageGenerationModelArchitecture
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_GENERATION, ModelDriverType.HUGGINGFACE)
class HuggingfaceImageGenerationTaskDriver:
    """Architecture dispatcher for the HuggingFace image-generation driver.

    The outer registry entry returns this class; `__new__` instantiates the
    per-architecture driver based on `component.architecture`.
    """

    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.architecture == HuggingfaceImageGenerationModelArchitecture.SDXL:
            from .architectures.sdxl import SdxlHuggingfaceImageGenerationTaskDriver
            return SdxlHuggingfaceImageGenerationTaskDriver(id, config, daemon)

        if config.architecture == HuggingfaceImageGenerationModelArchitecture.FLUX:
            from .architectures.flux import FluxHuggingfaceImageGenerationTaskDriver
            return FluxHuggingfaceImageGenerationTaskDriver(id, config, daemon)

        if config.architecture == HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE:
            from .architectures.hunyuan_image import HunyuanImageHuggingfaceImageGenerationTaskDriver
            return HunyuanImageHuggingfaceImageGenerationTaskDriver(id, config, daemon)

        if config.architecture == HuggingfaceImageGenerationModelArchitecture.QWEN_IMAGE:
            from .architectures.qwen_image import QwenImageHuggingfaceImageGenerationTaskDriver
            return QwenImageHuggingfaceImageGenerationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown architecture: {config.architecture}")
