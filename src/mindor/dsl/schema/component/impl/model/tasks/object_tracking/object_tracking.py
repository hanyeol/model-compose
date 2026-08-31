from typing import Union, Annotated
from pydantic import Field
from .impl import *

ObjectTrackingModelComponentConfig = Annotated[
    Union[
        CustomObjectTrackingModelComponentConfig,
    ],
    Field(discriminator="driver")
]
