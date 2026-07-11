from typing import Union, Annotated
from pydantic import Field
from .impl import *

FaceSwapModelComponentConfig = Annotated[
    Union[
        CustomFaceSwapModelComponentConfig,
    ],
    Field(discriminator="driver")
]
