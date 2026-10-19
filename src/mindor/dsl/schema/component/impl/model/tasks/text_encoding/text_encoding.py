from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextEncodingModelComponentConfig = Annotated[
    Union[
        HuggingfaceTextEncodingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
