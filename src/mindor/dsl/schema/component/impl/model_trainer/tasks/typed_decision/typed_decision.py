from typing import Union, Annotated
from pydantic import Field
from .impl import *

TypedDecisionModelTrainerComponentConfig = Annotated[
    Union[
        NimbleTypedDecisionModelTrainerComponentConfig,
        ClefTypedDecisionModelTrainerComponentConfig,
        KevTypedDecisionModelTrainerComponentConfig,
        LayaTypedDecisionModelTrainerComponentConfig,
    ],
    Field(discriminator="driver")
]
