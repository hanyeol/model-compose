from typing import Union, Annotated
from pydantic import Field
from .impl import *

VisionTextEncodingModelComponentConfig = Annotated[
    Union[
        HuggingfaceVisionTextEncodingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
