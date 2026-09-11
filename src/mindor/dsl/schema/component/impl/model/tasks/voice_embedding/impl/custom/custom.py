from typing import Union, Annotated
from pydantic import Field
from .pyannote import PyannoteVoiceEmbeddingModelComponentConfig

CustomVoiceEmbeddingModelComponentConfig = Annotated[
    Union[
        PyannoteVoiceEmbeddingModelComponentConfig,
    ],
    Field(discriminator="family")
]
