from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextRerankingModelComponentConfig = Annotated[
    Union[
        HuggingfaceTextRerankingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
