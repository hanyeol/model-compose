from typing import Union, Annotated
from pydantic import Field
from .minimax_h3 import MinimaxH3ImageGenerationModelComponentConfig

CustomImageGenerationModelComponentConfig = Annotated[
    Union[
        MinimaxH3ImageGenerationModelComponentConfig,
    ],
    Field(discriminator="family")
]
