from typing import Union, Annotated
from pydantic import Field
from .impl import *

TypedDecisionModelComponentConfig = Annotated[
    Union[
        CustomTypedDecisionModelComponentConfig,
    ],
    Field(discriminator="driver")
]
