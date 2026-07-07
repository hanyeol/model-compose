from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

AudioFeatureExtractorComponentConfig = Annotated[
    Union[
        FFmpegAudioFeatureExtractorComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.AUDIO_FEATURE_EXTRACTOR, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = AudioFeatureExtractorDriver.FFMPEG
