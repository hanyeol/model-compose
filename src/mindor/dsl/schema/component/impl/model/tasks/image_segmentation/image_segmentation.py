from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageSegmentationModelComponentConfig = Annotated[
    Union[
        CustomImageSegmentationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
