from typing import Union, Annotated
from pydantic import Field
from .impl import *

MusicEmbeddingModelComponentConfig = Annotated[
    Union[
        CustomMusicEmbeddingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
