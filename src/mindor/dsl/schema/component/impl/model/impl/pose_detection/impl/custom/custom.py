from typing import Union, Annotated
from pydantic import Field
from .impl.mediapipe import BlazePosePoseDetectionModelComponentConfig
from .impl.yolo import YoloPoseDetectionModelComponentConfig

CustomPoseDetectionModelComponentConfig = Annotated[
    Union[
        BlazePosePoseDetectionModelComponentConfig,
        YoloPoseDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
