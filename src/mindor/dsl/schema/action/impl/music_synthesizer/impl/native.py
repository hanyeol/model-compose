from typing import Union, Annotated
from pydantic import Field
from .common import (
    MusicSynthesizerSequenceActionConfig,
)

NativeMusicSynthesizerActionConfig = Annotated[
    Union[
        MusicSynthesizerSequenceActionConfig,
    ],
    Field(discriminator="method")
]
