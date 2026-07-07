from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

VideoFrameExtractorComponentConfig = Annotated[
    Union[
        FFmpegVideoFrameExtractorComponentConfig,
        OpencvVideoFrameExtractorComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.VIDEO_FRAME_EXTRACTOR, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = VideoFrameExtractorDriver.FFMPEG
