from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

MusicSegmentDetectorComponentConfig = Annotated[
    Union[
        NativeMusicSegmentDetectorComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.MUSIC_SEGMENT_DETECTOR, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = MusicSegmentDetectorDriver.NATIVE
