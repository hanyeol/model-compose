from typing import Union, Annotated
from pydantic import Field
from .impl.transnetv2 import TransNetV2ShotBoundaryDetectionModelComponentConfig

CustomShotBoundaryDetectionModelComponentConfig = Annotated[
    Union[
        TransNetV2ShotBoundaryDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
