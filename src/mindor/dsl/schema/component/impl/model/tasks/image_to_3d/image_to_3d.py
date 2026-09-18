from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageTo3DModelComponentConfig = Annotated[
    Union[
        CustomImageTo3DModelComponentConfig,
    ],
    Field(discriminator="driver")
]
