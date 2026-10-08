from typing import Union, Annotated
from pydantic import Field
from .impl import *

MusicPitchEstimationModelComponentConfig = Annotated[
    Union[
        CustomMusicPitchEstimationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
