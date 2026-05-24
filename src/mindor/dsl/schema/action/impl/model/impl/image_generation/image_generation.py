from typing import Union
from .impl import *

ImageGenerationModelActionConfig = Union[
    HunyuanImageGenerationModelActionConfig,
    FluxImageGenerationModelActionConfig,
    SdxlImageGenerationModelActionConfig,
]
