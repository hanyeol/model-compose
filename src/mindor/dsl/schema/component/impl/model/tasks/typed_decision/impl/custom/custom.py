from typing import Union, Annotated
from pydantic import Field
from .nimble import NimbleTypedDecisionModelComponentConfig

CustomTypedDecisionModelComponentConfig = Annotated[
    Union[
        NimbleTypedDecisionModelComponentConfig,
    ],
    Field(discriminator="family")
]
