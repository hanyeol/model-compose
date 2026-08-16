from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

ImageCompressorComponentConfig = Annotated[
    Union[
        NativeImageCompressorComponentConfig,
        OxipngImageCompressorComponentConfig,
        PngquantImageCompressorComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.IMAGE_COMPRESSOR, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = ImageCompressorDriver.NATIVE
