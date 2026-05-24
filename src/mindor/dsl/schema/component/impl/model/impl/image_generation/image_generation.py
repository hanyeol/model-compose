from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageGenerationModelComponentConfig = Annotated[
    Union[
        CustomImageGenerationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
