from typing import Union, Annotated
from pydantic import Field
from .impl import *

ActiveSpeakerDetectionModelComponentConfig = Annotated[
    Union[
        CustomActiveSpeakerDetectionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
