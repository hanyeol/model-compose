from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

VideoSceneTransitionClassifierComponentConfig = Annotated[
    Union[
        NativeVideoSceneTransitionClassifierComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.VIDEO_SCENE_TRANSITION_CLASSIFIER, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = VideoSceneTransitionClassifierDriverType.NATIVE
