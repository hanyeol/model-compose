from typing import Union, Annotated
from pydantic import Field
from .impl import *

LipSyncModelComponentConfig = Annotated[
    Union[
        CustomLipSyncModelComponentConfig,
    ],
    Field(discriminator="driver")
]
