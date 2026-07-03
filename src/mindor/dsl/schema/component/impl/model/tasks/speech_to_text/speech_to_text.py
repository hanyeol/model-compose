from typing import Union, Annotated
from pydantic import Field
from .impl import *

SpeechToTextModelComponentConfig = Annotated[
    Union[
        HuggingfaceSpeechToTextModelComponentConfig,
        CustomSpeechToTextModelComponentConfig,
    ],
    Field(discriminator="driver")
]
