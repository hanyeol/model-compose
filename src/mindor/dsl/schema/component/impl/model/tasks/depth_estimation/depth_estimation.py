from typing import Union, Annotated
from pydantic import Field
from .impl import *

DepthEstimationModelComponentConfig = Annotated[
    Union[
        HuggingfaceDepthEstimationModelComponentConfig,
    ],
    Field(discriminator="driver")
]
