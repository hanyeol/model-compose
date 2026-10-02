from typing import List, Literal, Optional
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from .common import CommonTypedDecisionModelTrainerComponentConfig
from ...common import ModelTrainerDriverType

class LayaTrainerPreset(str, Enum):
    ENGLISH         = "english"
    MULTILINGUAL    = "multilingual"
    TYPED_DECISIONS = "typed-decisions"

class LayaTypedDecisionModelTrainerComponentConfig(CommonTypedDecisionModelTrainerComponentConfig):
    driver: Literal[ModelTrainerDriverType.LAYA]
    preset: LayaTrainerPreset = Field(default=LayaTrainerPreset.MULTILINGUAL, description="Laya starting checkpoint; selects which encoder bundle subfolder to warm-start from.")
    freeze_encoder: bool = Field(default=True, description="Whether the encoder backbone is frozen and only the per-question heads are trained.")
    max_seq_length: Optional[int] = Field(default=None, description="Encoder token budget during training; overrides the checkpoint default.")
    max_head_length: Optional[int] = Field(default=None, description="Per-question head token budget during training; overrides the checkpoint default.")
    actions: List[TypedDecisionModelTrainerActionConfig] = Field(default_factory=list, description="Actions this typed-decision trainer component exposes to workflows.")
