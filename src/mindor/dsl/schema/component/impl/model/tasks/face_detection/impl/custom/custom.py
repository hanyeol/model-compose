from typing import Union, Annotated
from pydantic import Field
from .mediapipe import BlazeFaceFaceDetectionModelComponentConfig
from .insightface import InsightfaceFaceDetectionModelComponentConfig
from .ultralytics import YoloFaceDetectionModelComponentConfig

CustomFaceDetectionModelComponentConfig = Annotated[
    Union[
        BlazeFaceFaceDetectionModelComponentConfig,
        InsightfaceFaceDetectionModelComponentConfig,
        YoloFaceDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
