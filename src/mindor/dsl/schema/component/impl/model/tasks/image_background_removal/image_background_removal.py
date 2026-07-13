from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageBackgroundRemovalModelComponentConfig = Annotated[
    Union[
        HuggingfaceImageBackgroundRemovalModelComponentConfig,
    ],
    Field(discriminator="driver")
]
