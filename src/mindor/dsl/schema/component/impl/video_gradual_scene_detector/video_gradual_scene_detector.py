from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

VideoGradualSceneDetectorComponentConfig = Annotated[
    Union[
        OpenCvVideoGradualSceneDetectorComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.VIDEO_GRADUAL_SCENE_DETECTOR, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = VideoGradualSceneDetectorDriverType.OPENCV
