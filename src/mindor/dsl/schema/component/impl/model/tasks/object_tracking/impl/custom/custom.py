from typing import Union, Annotated
from pydantic import Field
from .impl.yolo import YoloObjectTrackingModelComponentConfig

CustomObjectTrackingModelComponentConfig = Annotated[
    Union[
        YoloObjectTrackingModelComponentConfig,
    ],
    Field(discriminator="family")
]
