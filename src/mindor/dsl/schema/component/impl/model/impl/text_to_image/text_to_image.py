from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextToImageModelComponentConfig = Annotated[
    Union[
        HuggingfaceTextToImageModelComponentConfig,
        CustomTextToImageModelComponentConfig,
    ],
    Field(discriminator="driver")
]
