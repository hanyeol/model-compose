from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextToTextModelComponentConfig = Annotated[
    Union[
        HuggingfaceTextToTextModelComponentConfig,
        CustomTextToTextModelComponentConfig,
    ],
    Field(discriminator="driver")
]
