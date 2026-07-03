from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageTextToTextModelComponentConfig = Annotated[
    Union[
        HuggingfaceImageTextToTextModelComponentConfig,
        VllmImageTextToTextModelComponentConfig,
        CustomImageTextToTextModelComponentConfig,
    ],
    Field(discriminator="driver")
]
