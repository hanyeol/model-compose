from typing import Union, Annotated
from pydantic import Field
from .pyannote import PyannoteSpeakerDiarizationModelComponentConfig

CustomSpeakerDiarizationModelComponentConfig = Annotated[
    Union[
        PyannoteSpeakerDiarizationModelComponentConfig,
    ],
    Field(discriminator="family")
]
