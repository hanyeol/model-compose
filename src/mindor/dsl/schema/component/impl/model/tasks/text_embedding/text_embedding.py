from typing import Union, Annotated
from pydantic import Field
from .impl import *

TextEmbeddingModelComponentConfig = Annotated[
    Union[
        HuggingfaceTextEmbeddingModelComponentConfig,
        LlamaCppTextEmbeddingModelComponentConfig,
        VllmTextEmbeddingModelComponentConfig,
        SglangTextEmbeddingModelComponentConfig,
        CustomTextEmbeddingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
