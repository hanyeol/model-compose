from typing import Union, Annotated
from pydantic import Field
from .impl import *

FaceEmbeddingModelComponentConfig = Annotated[
    Union[
        CustomFaceEmbeddingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
