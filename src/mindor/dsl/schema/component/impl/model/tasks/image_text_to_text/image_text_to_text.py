from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageTextToTextModelComponentConfig = Annotated[
    Union[
        HuggingfaceImageTextToTextModelComponentConfig,
        VllmImageTextToTextModelComponentConfig,
        SglangImageTextToTextModelComponentConfig,
        CustomImageTextToTextModelComponentConfig,
    ],
    Field(discriminator="driver")
]
