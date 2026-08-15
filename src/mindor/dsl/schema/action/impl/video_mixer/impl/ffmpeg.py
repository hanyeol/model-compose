from typing import Union, Annotated
from pydantic import Field
from .common import (
    VideoMixerConcatActionConfig,
    VideoMixerOverlayActionConfig,
)

FFmpegVideoMixerActionConfig = Annotated[
    Union[
        VideoMixerConcatActionConfig,
        VideoMixerOverlayActionConfig,
    ],
    Field(discriminator="method")
]
