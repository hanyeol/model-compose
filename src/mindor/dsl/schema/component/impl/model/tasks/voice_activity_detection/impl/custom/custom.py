from typing import Union, Annotated
from pydantic import Field
from .silero import SileroVoiceActivityDetectionModelComponentConfig

CustomVoiceActivityDetectionModelComponentConfig = Annotated[
    Union[
        SileroVoiceActivityDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
