from typing import Union, Annotated
from pydantic import Field
from .mediapipe import BlazeHandHandDetectionModelComponentConfig

CustomHandDetectionModelComponentConfig = Annotated[
    Union[
        BlazeHandHandDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
