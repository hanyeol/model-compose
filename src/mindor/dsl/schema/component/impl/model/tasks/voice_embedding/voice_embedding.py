from typing import Union, Annotated
from pydantic import Field
from .impl import *

VoiceEmbeddingModelComponentConfig = Annotated[
    Union[
        CustomVoiceEmbeddingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
