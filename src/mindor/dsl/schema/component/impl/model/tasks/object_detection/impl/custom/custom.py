from typing import Union, Annotated
from pydantic import Field
from .impl.yolo import YoloObjectDetectionModelComponentConfig

CustomObjectDetectionModelComponentConfig = Annotated[
    Union[
        YoloObjectDetectionModelComponentConfig,
    ],
    Field(discriminator="family")
]
