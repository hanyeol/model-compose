from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageToVideoModelComponentConfig = Annotated[
    Union[
        CustomImageToVideoModelComponentConfig,
    ],
    Field(discriminator="driver")
]
