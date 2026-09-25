from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TypedDecisionModelActionConfig
from ..common import CommonTypedDecisionModelComponentConfig
from .common import TypedDecisionModelFamily
from ....common import ModelDriverType

class KevBackend(str, Enum):
    AUTO  = "auto"
    TORCH = "torch"
    MLX   = "mlx"

class KevTypedDecisionModelComponentConfig(CommonTypedDecisionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TypedDecisionModelFamily.KEV]
    backend: KevBackend = Field(default=KevBackend.AUTO, description="Inference backend; 'auto' picks MLX on Apple Silicon hybrid bases and torch otherwise.")
    max_state_length: int = Field(default=8192, description="Maximum tokens allotted to the state (shared context) portion of the prompt.")
    max_branch_length: int = Field(default=8192, description="Maximum tokens allotted to per-question branches.")
    actions: List[TypedDecisionModelActionConfig] = Field(default_factory=list, description="Actions this typed decision component exposes to workflows.")
