from typing import Union
from .mediapipe import BlazeFaceFaceDetectionModelActionConfig
from .insightface import InsightfaceFaceDetectionModelActionConfig
from .ultralytics import YoloFaceDetectionModelActionConfig

CustomFaceDetectionModelActionConfig = Union[
    BlazeFaceFaceDetectionModelActionConfig,
    InsightfaceFaceDetectionModelActionConfig,
    YoloFaceDetectionModelActionConfig,
]
