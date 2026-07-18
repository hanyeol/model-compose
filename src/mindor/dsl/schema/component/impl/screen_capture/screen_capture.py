from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

ScreenCaptureComponentConfig = Annotated[
    Union[
        FFmpegScreenCaptureComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.SCREEN_CAPTURE, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = ScreenCaptureDriver.FFMPEG
