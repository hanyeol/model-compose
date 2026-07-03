from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageUpscaleModelComponentConfig = Annotated[
    Union[
        CustomImageUpscaleModelComponentConfig,
    ],
    Field(discriminator="driver")
]
