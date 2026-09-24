from typing import Union, Annotated
from pydantic import Field
from .kev import KevTypedDecisionModelComponentConfig
from .nimble import NimbleTypedDecisionModelComponentConfig

CustomTypedDecisionModelComponentConfig = Annotated[
    Union[
        KevTypedDecisionModelComponentConfig,
        NimbleTypedDecisionModelComponentConfig,
    ],
    Field(discriminator="family")
]
