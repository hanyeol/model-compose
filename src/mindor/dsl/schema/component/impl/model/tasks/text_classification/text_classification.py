from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextClassificationModelComponentConfig = Annotated[
    Union[
        HuggingfaceTextClassificationModelComponentConfig,
        CustomTextClassificationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
