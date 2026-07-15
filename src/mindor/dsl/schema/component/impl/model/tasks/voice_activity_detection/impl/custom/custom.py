from typing import Union, Annotated
from pydantic import Field
from .impl.silero import SileroVoiceActivityDetectionModelComponentConfig

CustomVoiceActivityDetectionModelComponentConfig = Annotated[
    Union[
        SileroVoiceActivityDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
