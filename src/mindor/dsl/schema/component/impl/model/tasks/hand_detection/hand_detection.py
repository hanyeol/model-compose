from typing import Union, Annotated
from pydantic import Field
from .impl import *

HandDetectionModelComponentConfig = Annotated[
    Union[
        CustomHandDetectionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
