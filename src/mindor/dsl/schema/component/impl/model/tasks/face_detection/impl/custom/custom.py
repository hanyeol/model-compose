from typing import Union, Annotated
from pydantic import Field
from .impl.mediapipe import BlazeFaceFaceDetectionModelComponentConfig

CustomFaceDetectionModelComponentConfig = Annotated[
    Union[
        BlazeFaceFaceDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
