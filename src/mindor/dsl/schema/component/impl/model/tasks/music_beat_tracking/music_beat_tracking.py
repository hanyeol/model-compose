from typing import Union, Annotated
from pydantic import Field
from .impl import *

MusicBeatTrackingModelComponentConfig = Annotated[
    Union[
        CustomMusicBeatTrackingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
