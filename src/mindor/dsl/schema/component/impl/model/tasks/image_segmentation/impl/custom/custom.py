from typing import Union, Annotated
from pydantic import Field
from .ultralytics import SamImageSegmentationModelComponentConfig

CustomImageSegmentationModelComponentConfig = Annotated[
    Union[
        SamImageSegmentationModelComponentConfig,
    ],
    Field(discriminator="family")
]
