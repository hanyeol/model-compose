from typing import Union, Annotated
from pydantic import Field
from .impl import *

AudioSourceSeparationModelComponentConfig = Annotated[
    Union[
        CustomAudioSourceSeparationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
