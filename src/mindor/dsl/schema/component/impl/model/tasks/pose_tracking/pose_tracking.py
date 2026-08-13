from typing import Union, Annotated
from pydantic import Field
from .impl import *

PoseTrackingModelComponentConfig = Annotated[
    Union[
        CustomPoseTrackingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
