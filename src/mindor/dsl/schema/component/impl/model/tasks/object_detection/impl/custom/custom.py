from typing import Union, Annotated
from pydantic import Field
from .ultralytics import YoloObjectDetectionModelComponentConfig

CustomObjectDetectionModelComponentConfig = Annotated[
    Union[
        YoloObjectDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
