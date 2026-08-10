from typing import Union, Annotated
from pydantic import Field
from .impl.mediapipe import BlazeFaceFaceDetectionModelComponentConfig
from .impl.insightface import InsightfaceFaceDetectionModelComponentConfig

CustomFaceDetectionModelComponentConfig = Annotated[
    Union[
        BlazeFaceFaceDetectionModelComponentConfig,
        InsightfaceFaceDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
