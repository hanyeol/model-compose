from typing import Union, Annotated
from pydantic import Field
from .birefnet import BiRefNetImageBackgroundRemovalModelComponentConfig
from .ben2 import Ben2ImageBackgroundRemovalModelComponentConfig

CustomImageBackgroundRemovalModelComponentConfig = Annotated[
    Union[
        BiRefNetImageBackgroundRemovalModelComponentConfig,
        Ben2ImageBackgroundRemovalModelComponentConfig,
    ],
    Field(discriminator="family")
]
