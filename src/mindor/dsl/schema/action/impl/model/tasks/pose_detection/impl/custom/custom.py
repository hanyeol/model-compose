from typing import Union
from .mediapipe import BlazePosePoseDetectionModelActionConfig
from .ultralytics import YoloPoseDetectionModelActionConfig

CustomPoseDetectionModelActionConfig = Union[
    BlazePosePoseDetectionModelActionConfig,
    YoloPoseDetectionModelActionConfig,
]
