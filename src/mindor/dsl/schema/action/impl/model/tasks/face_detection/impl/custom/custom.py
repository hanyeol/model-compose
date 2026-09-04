from typing import Union
from .mediapipe import BlazeFaceFaceDetectionModelActionConfig
from .insightface import InsightfaceFaceDetectionModelActionConfig

CustomFaceDetectionModelActionConfig = Union[
    BlazeFaceFaceDetectionModelActionConfig,
    InsightfaceFaceDetectionModelActionConfig,
]
