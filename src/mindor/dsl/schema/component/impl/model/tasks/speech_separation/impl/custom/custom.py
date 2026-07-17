from typing import Union, Annotated
from pydantic import Field
from .impl.sepformer import SepformerSpeechSeparationModelComponentConfig

CustomSpeechSeparationModelComponentConfig = Annotated[
    Union[
        SepformerSpeechSeparationModelComponentConfig,
    ],
    Field(discriminator="family")
]
