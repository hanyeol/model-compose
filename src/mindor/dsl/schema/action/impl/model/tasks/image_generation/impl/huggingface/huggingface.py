from typing import Union
from .impl.sdxl import SdxlHuggingfaceImageGenerationModelActionConfig
from .impl.flux import FluxHuggingfaceImageGenerationModelActionConfig
from .impl.flux2 import (
    Flux2HuggingfaceImageGenerationModelActionConfig,
    Flux2KleinHuggingfaceImageGenerationModelActionConfig,
)
from .impl.hunyuan_image import HunyuanImageHuggingfaceImageGenerationModelActionConfig
from .impl.qwen_image import QwenImageHuggingfaceImageGenerationModelActionConfig
from .impl.qwen_image_edit import QwenImageEditHuggingfaceImageGenerationModelActionConfig

HuggingfaceImageGenerationModelActionConfig = Union[
    SdxlHuggingfaceImageGenerationModelActionConfig,
    FluxHuggingfaceImageGenerationModelActionConfig,
    Flux2HuggingfaceImageGenerationModelActionConfig,
    Flux2KleinHuggingfaceImageGenerationModelActionConfig,
    HunyuanImageHuggingfaceImageGenerationModelActionConfig,
    QwenImageHuggingfaceImageGenerationModelActionConfig,
    QwenImageEditHuggingfaceImageGenerationModelActionConfig,
]
