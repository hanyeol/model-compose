from typing import Union, Annotated
from pydantic import Field
from .beat_this import BeatThisMusicBeatTrackingModelComponentConfig

CustomMusicBeatTrackingModelComponentConfig = Annotated[
    Union[
        BeatThisMusicBeatTrackingModelComponentConfig,
    ],
    Field(discriminator="family")
]
