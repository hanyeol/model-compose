from typing import Union, Annotated
from pydantic import Field
from .sam import SamImageSegmentationModelComponentConfig

CustomImageSegmentationModelComponentConfig = Annotated[
    Union[
        SamImageSegmentationModelComponentConfig,
    ],
    Field(discriminator="family")
]
