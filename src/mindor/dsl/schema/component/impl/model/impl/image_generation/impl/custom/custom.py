from typing import Union, Annotated
from enum import Enum
from pydantic import Field

class CustomImageGenerationModelFamily(str, Enum):
    SDXL          = "sdxl"
    FLUX          = "flux"
    HUNYUAN_IMAGE = "hunyuan-image"

from .hunyuan_image import HunyuanImageGenerationModelComponentConfig
from .flux import FluxImageGenerationModelComponentConfig
from .sdxl import SdxlImageGenerationModelComponentConfig

CustomImageGenerationModelComponentConfig = Annotated[
    Union[
        HunyuanImageGenerationModelComponentConfig,
        FluxImageGenerationModelComponentConfig,
        SdxlImageGenerationModelComponentConfig,
    ],
    Field(discriminator="family")
]
