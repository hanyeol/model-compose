from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageToTextModelComponentConfig = Annotated[
    Union[
        HuggingfaceImageToTextModelComponentConfig,
        CustomImageToTextModelComponentConfig,
    ],
    Field(discriminator="driver")
]
