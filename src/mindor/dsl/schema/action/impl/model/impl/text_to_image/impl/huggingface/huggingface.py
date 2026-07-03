from typing import Union
from .impl.sdxl import SdxlHuggingfaceTextToImageModelActionConfig
from .impl.flux import FluxHuggingfaceTextToImageModelActionConfig
from .impl.hunyuan_image import HunyuanImageHuggingfaceTextToImageModelActionConfig

HuggingfaceTextToImageModelActionConfig = Union[
    SdxlHuggingfaceTextToImageModelActionConfig,
    FluxHuggingfaceTextToImageModelActionConfig,
    HunyuanImageHuggingfaceTextToImageModelActionConfig,
]
