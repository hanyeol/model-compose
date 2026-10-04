from typing import Union, Annotated
from pydantic import Field
from .impl import *

VideoTextScoringModelComponentConfig = Annotated[
    Union[
        HuggingfaceVideoTextScoringModelComponentConfig,
        CustomVideoTextScoringModelComponentConfig,
    ],
    Field(discriminator="driver")
]
