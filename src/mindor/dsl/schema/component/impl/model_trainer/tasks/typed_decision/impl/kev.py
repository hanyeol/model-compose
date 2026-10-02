from typing import List, Literal
from pydantic import Field
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from .common import CommonTypedDecisionModelTrainerComponentConfig
from ...common import ModelTrainerDriverType

class KevTypedDecisionModelTrainerComponentConfig(CommonTypedDecisionModelTrainerComponentConfig):
    driver: Literal[ModelTrainerDriverType.KEV]
    max_state_length: int = Field(default=8192, description="Maximum tokens allotted to the state (shared context) portion of the prompt.")
    max_branch_length: int = Field(default=8192, description="Maximum tokens allotted to per-question branches.")
    train_pointer_head: bool = Field(default=True, description="Whether the pointer head weights are trained alongside the LoRA adapter.")
    actions: List[TypedDecisionModelTrainerActionConfig] = Field(default_factory=list, description="Actions this typed-decision trainer component exposes to workflows.")
