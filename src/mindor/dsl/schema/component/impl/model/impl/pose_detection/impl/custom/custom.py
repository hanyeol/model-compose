from typing import Union, Annotated
from pydantic import Field
from .impl.mediapipe import BlazePosePoseDetectionModelComponentConfig

CustomPoseDetectionModelComponentConfig = Annotated[
    Union[
        BlazePosePoseDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
