from typing import Union, Annotated
from pydantic import Field
from .impl import *

MusicSourceSeparationModelComponentConfig = Annotated[
    Union[
        CustomMusicSourceSeparationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
