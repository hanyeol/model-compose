from typing import Union, Annotated
from pydantic import Field
from .wav2lip import Wav2LipLipSyncModelComponentConfig
from .latentsync import LatentSyncLipSyncModelComponentConfig
from .musetalk import MuseTalkLipSyncModelComponentConfig

CustomLipSyncModelComponentConfig = Annotated[
    Union[
        Wav2LipLipSyncModelComponentConfig,
        LatentSyncLipSyncModelComponentConfig,
        MuseTalkLipSyncModelComponentConfig,
    ],
    Field(discriminator="family")
]
