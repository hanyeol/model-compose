from typing import Union, Annotated
from pydantic import Field
from .impl import *

HumanMeshRecoveryModelComponentConfig = Annotated[
    Union[
        CustomHumanMeshRecoveryModelComponentConfig,
    ],
    Field(discriminator="driver")
]
