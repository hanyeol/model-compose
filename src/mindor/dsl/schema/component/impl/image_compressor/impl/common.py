from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class ImageCompressorDriverType(str, Enum):
    NATIVE   = "native"
    OXIPNG   = "oxipng"
    PNGQUANT = "pngquant"

class CommonImageCompressorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.IMAGE_COMPRESSOR]
    driver: ImageCompressorDriverType = Field(..., description="Backend implementation used to compress images.")
