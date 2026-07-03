from typing import Union, Annotated
from pydantic import Field
from .impl import *

MusicGenerationModelComponentConfig = Annotated[
    Union[
        CustomMusicGenerationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
