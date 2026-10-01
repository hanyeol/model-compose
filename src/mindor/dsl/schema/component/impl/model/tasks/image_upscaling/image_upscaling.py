from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageUpscalingModelComponentConfig = Annotated[
    Union[
        CustomImageUpscalingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
