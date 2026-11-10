from typing import Union, Annotated
from pydantic import Field
from .impl import *

ImageDeblurringModelComponentConfig = Annotated[
    Union[
        CustomImageDeblurringModelComponentConfig,
    ],
    Field(discriminator="driver")
]
