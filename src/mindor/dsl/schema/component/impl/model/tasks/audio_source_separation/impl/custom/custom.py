from typing import Union, Annotated
from pydantic import Field
from .sam_audio import SamAudioAudioSourceSeparationModelComponentConfig

CustomAudioSourceSeparationModelComponentConfig = Annotated[
    Union[
        SamAudioAudioSourceSeparationModelComponentConfig,
    ],
    Field(discriminator="family")
]
