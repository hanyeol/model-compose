from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class ImageCompressorDriver(str, Enum):
    NATIVE   = "native"
    OXIPNG   = "oxipng"
    PNGQUANT = "pngquant"

class CommonImageCompressorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.IMAGE_COMPRESSOR]
    driver: ImageCompressorDriver = Field(..., description="Backend implementation used to compress images.")
