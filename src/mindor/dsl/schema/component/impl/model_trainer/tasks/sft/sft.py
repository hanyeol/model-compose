from typing import Union, Annotated
from pydantic import Field
from .impl import *

SftModelTrainerComponentConfig = Annotated[
    Union[
        HuggingfaceSftModelTrainerComponentConfig,
    ],
    Field(discriminator="driver")
]
