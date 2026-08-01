from typing import Union, Annotated
from pydantic import Field
from .impl import *

AudioTextAlignmentModelComponentConfig = Annotated[
    Union[
        HuggingfaceAudioTextAlignmentModelComponentConfig,
    ],
    Field(discriminator="driver")
]
