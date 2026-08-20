from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextToVideoModelComponentConfig = Annotated[
    Union[
        CustomTextToVideoModelComponentConfig,
    ],
    Field(discriminator="driver")
]
