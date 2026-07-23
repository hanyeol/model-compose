from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

AudioPlaybackComponentConfig = Annotated[
    Union[
        FFmpegAudioPlaybackComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.AUDIO_PLAYBACK, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = AudioPlaybackDriver.FFMPEG
