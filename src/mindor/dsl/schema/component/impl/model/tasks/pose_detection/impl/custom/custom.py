from typing import Union, Annotated
from pydantic import Field
from .mediapipe import BlazePosePoseDetectionModelComponentConfig
from .ultralytics import YoloPoseDetectionModelComponentConfig

CustomPoseDetectionModelComponentConfig = Annotated[
    Union[
        BlazePosePoseDetectionModelComponentConfig,
        YoloPoseDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
