from typing import Union, Annotated
from pydantic import Field
from .impl import *

ShotBoundaryDetectionModelComponentConfig = Annotated[
    Union[
        CustomShotBoundaryDetectionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
