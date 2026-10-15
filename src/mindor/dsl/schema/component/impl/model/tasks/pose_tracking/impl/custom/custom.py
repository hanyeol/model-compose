from typing import Union, Annotated
from pydantic import Field
from .ultralytics import YoloPoseTrackingModelComponentConfig

CustomPoseTrackingModelComponentConfig = Annotated[
    Union[
        YoloPoseTrackingModelComponentConfig,
    ],
    Field(discriminator="family")
]
