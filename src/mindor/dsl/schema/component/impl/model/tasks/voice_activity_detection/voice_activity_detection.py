from typing import Union, Annotated
from pydantic import Field
from .impl import *

VoiceActivityDetectionModelComponentConfig = Annotated[
    Union[
        CustomVoiceActivityDetectionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
