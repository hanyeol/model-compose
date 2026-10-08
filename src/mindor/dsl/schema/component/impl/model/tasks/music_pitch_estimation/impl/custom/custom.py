from typing import Union, Annotated
from pydantic import Field
from .pesto import PestoMusicPitchEstimationModelComponentConfig

CustomMusicPitchEstimationModelComponentConfig = Annotated[
    Union[
        PestoMusicPitchEstimationModelComponentConfig,
    ],
    Field(discriminator="family")
]
