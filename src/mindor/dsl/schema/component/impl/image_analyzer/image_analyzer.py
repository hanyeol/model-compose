from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

ImageAnalyzerComponentConfig = Annotated[
    Union[
        NativeImageAnalyzerComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.IMAGE_ANALYZER, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = ImageAnalyzerDriver.NATIVE
