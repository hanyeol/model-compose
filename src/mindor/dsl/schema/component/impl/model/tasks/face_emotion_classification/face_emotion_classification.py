from typing import Union, Annotated
from pydantic import Field
from .impl import *

FaceEmotionClassificationModelComponentConfig = Annotated[
    Union[
        CustomFaceEmotionClassificationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
