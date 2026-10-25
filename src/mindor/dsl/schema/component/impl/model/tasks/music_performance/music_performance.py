from typing import Union, Annotated
from pydantic import Field
from .impl import *

MusicPerformanceModelComponentConfig = Annotated[
    Union[
        CustomMusicPerformanceModelComponentConfig,
    ],
    Field(discriminator="driver")
]
