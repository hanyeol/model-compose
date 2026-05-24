from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextToSpeechModelComponentConfig = Annotated[
    Union[
        CustomTextToSpeechModelComponentConfig,
    ],
    Field(discriminator="driver")
]
