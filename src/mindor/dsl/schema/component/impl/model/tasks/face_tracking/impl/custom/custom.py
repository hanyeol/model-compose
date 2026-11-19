from typing import Union, Annotated
from pydantic import Field
from .insightface import InsightfaceFaceTrackingModelComponentConfig
from .ultralytics import YoloFaceTrackingModelComponentConfig

CustomFaceTrackingModelComponentConfig = Annotated[
    Union[
        InsightfaceFaceTrackingModelComponentConfig,
        YoloFaceTrackingModelComponentConfig,
    ],
    Field(discriminator="family")
]
