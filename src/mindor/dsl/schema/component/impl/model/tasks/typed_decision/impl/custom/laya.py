from typing import Literal, Optional, List
from pydantic import Field
from mindor.dsl.schema.action import TypedDecisionModelActionConfig
from ..common import CommonTypedDecisionModelComponentConfig
from .common import TypedDecisionModelFamily
from ....common import ModelDriverType

class LayaTypedDecisionModelComponentConfig(CommonTypedDecisionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TypedDecisionModelFamily.LAYA]
    subfolder: Optional[str] = Field(default=None, description="Checkpoint subfolder within a bundle repo (e.g. 'multilingual', 'typed-decisions').")
    max_len: Optional[int] = Field(default=None, description="Per-call encoder token budget; overrides the checkpoint default.")
    head_max_len: Optional[int] = Field(default=None, description="Per-call per-question head token budget; overrides the checkpoint default.")
    fast: bool = Field(default=False, description="Enable the TileLang CUDA fast path (requires laya[fast]).")
    actions: List[TypedDecisionModelActionConfig] = Field(default_factory=list, description="Actions this typed decision component exposes to workflows.")
