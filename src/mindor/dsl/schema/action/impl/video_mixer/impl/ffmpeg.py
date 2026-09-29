from typing import Union, Annotated
from pydantic import Field
from .common import (
    VideoMixerOverlayActionConfig,
    VideoMixerConcatActionConfig,
)

FFmpegVideoMixerActionConfig = Annotated[
    Union[
        VideoMixerOverlayActionConfig,
        VideoMixerConcatActionConfig,
    ],
    Field(discriminator="method")
]
