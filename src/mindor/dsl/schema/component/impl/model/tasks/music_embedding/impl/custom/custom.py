from typing import Union, Annotated
from pydantic import Field
from .sampleid import SampleidMusicEmbeddingModelComponentConfig

CustomMusicEmbeddingModelComponentConfig = Annotated[
    Union[
        SampleidMusicEmbeddingModelComponentConfig,
    ],
    Field(discriminator="family")
]
