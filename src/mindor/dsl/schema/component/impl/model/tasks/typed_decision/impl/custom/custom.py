from typing import Union, Annotated
from pydantic import Field
from .kev import KevTypedDecisionModelComponentConfig
from .nimble import NimbleTypedDecisionModelComponentConfig
from .laya import LayaTypedDecisionModelComponentConfig
from .clef import ClefTypedDecisionModelComponentConfig

CustomTypedDecisionModelComponentConfig = Annotated[
    Union[
        KevTypedDecisionModelComponentConfig,
        NimbleTypedDecisionModelComponentConfig,
        LayaTypedDecisionModelComponentConfig,
        ClefTypedDecisionModelComponentConfig,
    ],
    Field(discriminator="family")
]
