from typing import Union, Annotated
from pydantic import Field
from .impl.sam import SamImageSegmentationModelComponentConfig

CustomImageSegmentationModelComponentConfig = Annotated[
    Union[
        SamImageSegmentationModelComponentConfig,
    ],
    Field(discriminator="family")
]
