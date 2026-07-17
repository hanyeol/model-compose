from typing import Union, Annotated
from pydantic import Field
from .impl.pyannote import PyannoteSpeakerDiarizationModelComponentConfig

CustomSpeakerDiarizationModelComponentConfig = Annotated[
    Union[
        PyannoteSpeakerDiarizationModelComponentConfig,
    ],
    Field(discriminator="family")
]
