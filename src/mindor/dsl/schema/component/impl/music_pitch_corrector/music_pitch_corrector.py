from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

MusicPitchCorrectorComponentConfig = Annotated[
    Union[
        WorldMusicPitchCorrectorComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.MUSIC_PITCH_CORRECTOR, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = MusicPitchCorrectorDriverType.WORLD
