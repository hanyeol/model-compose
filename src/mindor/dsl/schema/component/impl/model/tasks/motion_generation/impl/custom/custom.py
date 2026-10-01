from typing import Union, Annotated
from pydantic import Field
from .kimodo import KimodoMotionGenerationModelComponentConfig

CustomMotionGenerationModelComponentConfig = Annotated[
    Union[
        KimodoMotionGenerationModelComponentConfig,
    ],
    Field(discriminator="family")
]
