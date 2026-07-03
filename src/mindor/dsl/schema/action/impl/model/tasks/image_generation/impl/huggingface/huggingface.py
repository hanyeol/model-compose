from typing import Union
from .impl.sdxl import SdxlHuggingfaceImageGenerationModelActionConfig
from .impl.flux import FluxHuggingfaceImageGenerationModelActionConfig
from .impl.hunyuan_image import HunyuanImageHuggingfaceImageGenerationModelActionConfig

HuggingfaceImageGenerationModelActionConfig = Union[
    SdxlHuggingfaceImageGenerationModelActionConfig,
    FluxHuggingfaceImageGenerationModelActionConfig,
    HunyuanImageHuggingfaceImageGenerationModelActionConfig,
]
