from typing import Any, Dict, List, Literal
from pydantic import Field, model_validator
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from mindor.dsl.schema.component.impl.model import ModelConfig, ModelProvider
from .common import CommonTypedDecisionModelTrainerComponentConfig
from ...common import ModelTrainerDriverType

class NimbleTypedDecisionModelTrainerComponentConfig(CommonTypedDecisionModelTrainerComponentConfig):
    driver: Literal[ModelTrainerDriverType.NIMBLE]
    base_model: ModelConfig = Field(..., description="Base model the LoRA adapter is trained on top of — a HuggingFace repo ID or a local path.")
    max_seq_length: int = Field(default=4096, description="Maximum tokenized sequence length used during training.")
    actions: List[TypedDecisionModelTrainerActionConfig] = Field(default_factory=list, description="Actions this typed-decision trainer component exposes to workflows.")

    @model_validator(mode="before")
    def resolve_base_model(cls, values: Dict[str, Any]):
        base_model = values.get("base_model")
        if isinstance(base_model, str):
            if is_local_path(base_model):
                values["base_model"] = { "provider": ModelProvider.LOCAL, "path": base_model }
            else:
                values["base_model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": base_model }
        return values
