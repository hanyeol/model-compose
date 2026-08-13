from typing import Union, Annotated
from pydantic import Field
from .impl.yolo import YoloPoseTrackingModelComponentConfig

CustomPoseTrackingModelComponentConfig = Annotated[
    Union[
        YoloPoseTrackingModelComponentConfig,
    ],
    Field(discriminator="family")
]
