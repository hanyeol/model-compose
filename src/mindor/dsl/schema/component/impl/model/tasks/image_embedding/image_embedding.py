from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageEmbeddingModelComponentConfig = Annotated[
    Union[
        HuggingfaceImageEmbeddingModelComponentConfig,
        CustomImageEmbeddingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
