from typing import Union, Annotated
from pydantic import Field
from .impl import *

SpeechSeparationModelComponentConfig = Annotated[
    Union[
        CustomSpeechSeparationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
