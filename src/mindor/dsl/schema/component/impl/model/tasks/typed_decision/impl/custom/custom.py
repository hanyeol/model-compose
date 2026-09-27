from typing import Union, Annotated
from pydantic import Field
from .kev import KevTypedDecisionModelComponentConfig
from .nimble import NimbleTypedDecisionModelComponentConfig
from .laya import LayaTypedDecisionModelComponentConfig

CustomTypedDecisionModelComponentConfig = Annotated[
    Union[
        KevTypedDecisionModelComponentConfig,
        NimbleTypedDecisionModelComponentConfig,
        LayaTypedDecisionModelComponentConfig,
    ],
    Field(discriminator="family")
]
