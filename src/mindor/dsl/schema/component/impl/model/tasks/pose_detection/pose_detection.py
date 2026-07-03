from typing import Union, Annotated
from pydantic import Field
from .impl import *

PoseDetectionModelComponentConfig = Annotated[
    Union[
        CustomPoseDetectionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
