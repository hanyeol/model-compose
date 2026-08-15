from typing import Union, Annotated
from pydantic import Field
from .common import (
    AudioMixerConcatActionConfig,
    AudioMixerOverlayActionConfig,
)

FFmpegAudioMixerActionConfig = Annotated[
    Union[
        AudioMixerConcatActionConfig,
        AudioMixerOverlayActionConfig,
    ],
    Field(discriminator="method")
]
