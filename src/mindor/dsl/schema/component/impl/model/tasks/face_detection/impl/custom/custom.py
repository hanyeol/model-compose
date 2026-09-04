from typing import Union, Annotated
from pydantic import Field
from .mediapipe import BlazeFaceFaceDetectionModelComponentConfig
from .insightface import InsightfaceFaceDetectionModelComponentConfig

CustomFaceDetectionModelComponentConfig = Annotated[
    Union[
        BlazeFaceFaceDetectionModelComponentConfig,
        InsightfaceFaceDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
