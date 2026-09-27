from typing import Union, Annotated
from pydantic import Field
from .impl import *

VideoToVideoModelComponentConfig = Annotated[
    Union[
        HuggingfaceVideoToVideoModelComponentConfig,
        CustomVideoToVideoModelComponentConfig,
    ],
    Field(discriminator="driver")
]
