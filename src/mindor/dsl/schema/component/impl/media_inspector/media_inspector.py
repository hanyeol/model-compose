from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

MediaInspectorComponentConfig = Annotated[
    Union[
        FFmpegMediaInspectorComponentConfig,
        ExiftoolMediaInspectorComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.MEDIA_INSPECTOR, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = MediaInspectorDriver.FFMPEG
