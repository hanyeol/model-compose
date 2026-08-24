from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

AudioSegmentDetectorComponentConfig = Annotated[
    Union[
        NativeAudioSegmentDetectorComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.AUDIO_SEGMENT_DETECTOR, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = AudioSegmentDetectorDriver.NATIVE
