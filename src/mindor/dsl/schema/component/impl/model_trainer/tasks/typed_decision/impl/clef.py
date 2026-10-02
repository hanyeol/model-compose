from typing import List, Literal
from pydantic import Field
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from .common import CommonTypedDecisionModelTrainerComponentConfig
from ...common import ModelTrainerDriverType

class ClefTypedDecisionModelTrainerComponentConfig(CommonTypedDecisionModelTrainerComponentConfig):
    driver: Literal[ModelTrainerDriverType.CLEF]
    choice_loss_weight: float = Field(default=1.0, description="Loss weight applied to choice-type questions.")
    noul_loss_weight: float = Field(default=1.0, description="Loss weight applied to noul-type (binary) questions.")
    score_loss_weight: float = Field(default=1.0, description="Loss weight applied to score-type (ordinal) questions.")
    actions: List[TypedDecisionModelTrainerActionConfig] = Field(default_factory=list, description="Actions this typed-decision trainer component exposes to workflows.")
