from typing import Union, Annotated
from pydantic import Field
from .impl import *

FaceDetectionModelComponentConfig = Annotated[
    Union[
        CustomFaceDetectionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
