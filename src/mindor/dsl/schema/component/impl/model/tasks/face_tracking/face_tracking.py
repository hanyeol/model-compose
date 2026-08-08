from typing import Union, Annotated
from pydantic import Field
from .impl import *

FaceTrackingModelComponentConfig = Annotated[
    Union[
        CustomFaceTrackingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
