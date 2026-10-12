from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageEdgeDetectionModelComponentConfig = Annotated[
    Union[
        CustomImageEdgeDetectionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
