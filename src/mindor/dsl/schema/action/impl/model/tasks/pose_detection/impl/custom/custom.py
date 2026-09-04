from typing import Union
from .mediapipe import BlazePosePoseDetectionModelActionConfig
from .yolo import YoloPoseDetectionModelActionConfig

CustomPoseDetectionModelActionConfig = Union[
    BlazePosePoseDetectionModelActionConfig,
    YoloPoseDetectionModelActionConfig,
]
