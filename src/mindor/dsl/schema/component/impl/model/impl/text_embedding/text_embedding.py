from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextEmbeddingModelComponentConfig = Annotated[
    Union[
        HuggingfaceTextEmbeddingModelComponentConfig,
        LlamaCppTextEmbeddingModelComponentConfig,
        VllmTextEmbeddingModelComponentConfig,
        CustomTextEmbeddingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
