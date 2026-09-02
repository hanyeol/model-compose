from typing import Union, Annotated
from pydantic import Field
from .impl import *

VideoEmbeddingModelComponentConfig = Annotated[
    Union[
        HuggingfaceVideoEmbeddingModelComponentConfig,
        CustomVideoEmbeddingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
