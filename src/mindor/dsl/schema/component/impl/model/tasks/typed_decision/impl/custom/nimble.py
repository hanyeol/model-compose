from typing import Any, Dict, Literal, List
from pydantic import Field, model_validator
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import TypedDecisionModelActionConfig
from ..common import CommonTypedDecisionModelComponentConfig
from .common import TypedDecisionModelFamily
from ....common import ModelConfig, ModelDriverType, ModelProvider

_DEFAULT_BASE_REPOSITORY = "Qwen/Qwen3.5-9B"

class NimbleTypedDecisionModelComponentConfig(CommonTypedDecisionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TypedDecisionModelFamily.NIMBLE]
    base_model: ModelConfig = Field(..., description="Base model the adapter is merged onto — a HuggingFace repo ID or a local path.")
    max_seq_length: int = Field(default=4096, description="Maximum sequence length (in tokens) the scorer accepts.")
    actions: List[TypedDecisionModelActionConfig] = Field(default_factory=list, description="Actions this typed decision component exposes to workflows.")

    @model_validator(mode="before")
    def resolve_base_model(cls, values: Dict[str, Any]):
        base_model = values.get("base_model")
        if base_model is None:
            base_model = _DEFAULT_BASE_REPOSITORY
        if isinstance(base_model, str):
            if is_local_path(base_model):
                values["base_model"] = { "provider": ModelProvider.LOCAL, "path": base_model }
            else:
                values["base_model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": base_model }
        return values
