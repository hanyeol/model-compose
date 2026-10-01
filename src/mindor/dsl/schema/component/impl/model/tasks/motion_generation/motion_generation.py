from typing import Union, Annotated
from pydantic import Field
from .impl import *

MotionGenerationModelComponentConfig = Annotated[
    Union[
        CustomMotionGenerationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
