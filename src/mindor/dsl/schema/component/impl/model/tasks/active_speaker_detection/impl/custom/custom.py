from typing import Union, Annotated
from pydantic import Field
from .light_asd import LightAsdActiveSpeakerDetectionModelComponentConfig

CustomActiveSpeakerDetectionModelComponentConfig = Annotated[
    Union[
        LightAsdActiveSpeakerDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
