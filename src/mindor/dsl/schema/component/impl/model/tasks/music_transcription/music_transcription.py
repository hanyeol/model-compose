from typing import Union, Annotated
from pydantic import Field
from .impl import *

MusicTranscriptionModelComponentConfig = Annotated[
    Union[
        CustomMusicTranscriptionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
