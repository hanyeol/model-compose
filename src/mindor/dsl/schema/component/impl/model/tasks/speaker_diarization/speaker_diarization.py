from typing import Union, Annotated
from pydantic import Field
from .impl import *

SpeakerDiarizationModelComponentConfig = Annotated[
    Union[
        CustomSpeakerDiarizationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
