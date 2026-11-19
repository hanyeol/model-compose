from typing import Union
from .insightface import InsightfaceFaceTrackingModelActionConfig
from .ultralytics import YoloFaceTrackingModelActionConfig

CustomFaceTrackingModelActionConfig = Union[
    InsightfaceFaceTrackingModelActionConfig,
    YoloFaceTrackingModelActionConfig,
]
