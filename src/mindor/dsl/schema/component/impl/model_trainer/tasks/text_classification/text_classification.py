from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextClassificationModelTrainerComponentConfig = Annotated[
    Union[
        HuggingfaceTextClassificationModelTrainerComponentConfig,
    ],
    Field(discriminator="driver")
]
