from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageTextScoringModelComponentConfig = Annotated[
    Union[
        HuggingfaceImageTextScoringModelComponentConfig,
        CustomImageTextScoringModelComponentConfig,
    ],
    Field(discriminator="driver")
]
