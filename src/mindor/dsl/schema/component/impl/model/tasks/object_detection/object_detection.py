from typing import Union, Annotated
from pydantic import Field
from .impl import *

ObjectDetectionModelComponentConfig = Annotated[
    Union[
        CustomObjectDetectionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
