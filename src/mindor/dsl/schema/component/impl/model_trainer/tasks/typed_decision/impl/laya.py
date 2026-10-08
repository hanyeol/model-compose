from typing import List, Literal, Optional, Union, Annotated, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import TypedDecisionModelTrainerActionConfig
from .common import CommonTypedDecisionModelTrainerComponentConfig
from ...common import ModelTrainerDriverType
from .....model.tasks.common import ModelProvider, HuggingfaceModelConfig, LocalModelConfig

# Convai Innovations ships all three checkpoints in a single repo, one per
# subfolder. Used as the fallback when the user provides neither `model` nor
# `preset`; the driver reads `preset` to pick which subfolder to warm-start
# from.
_DEFAULT_MODEL_REPOSITORY = "convaiinnovations/laya"

class LayaTrainerPreset(str, Enum):
    ENGLISH         = "english"
    MULTILINGUAL    = "multilingual"
    TYPED_DECISIONS = "typed-decisions"

LayaTypedDecisionModelTrainerModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class LayaTypedDecisionModelTrainerComponentConfig(CommonTypedDecisionModelTrainerComponentConfig):
    driver: Literal[ModelTrainerDriverType.LAYA]
    model: LayaTypedDecisionModelTrainerModelConfig = Field(..., description="Laya warm-start checkpoint — a HuggingFace repo ID or a local directory. Defaults to the bundle repo hosting all three presets.")
    preset: Optional[LayaTrainerPreset] = Field(default=None, description="Laya warm-start checkpoint: 'english' (ModernBERT-large), 'multilingual' (mmBERT-base, 100+ languages), or 'typed-decisions' (fine-tuned on the typed-decisions workflows).")
    freeze_encoder: bool = Field(default=True, description="Whether the encoder backbone is frozen and only the per-question heads are trained.")
    max_seq_length: Optional[int] = Field(default=None, description="Encoder token budget during training; overrides the checkpoint default.")
    max_head_length: Optional[int] = Field(default=None, description="Per-question head token budget during training; overrides the checkpoint default.")
    actions: List[TypedDecisionModelTrainerActionConfig] = Field(default_factory=list, description="Actions this typed-decision trainer component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model_from_preset(cls, values: Dict[str, Any]):
        # When the user supplies their own `model`, trust it as-is and leave
        # `preset` untouched. Only when neither is given do we fall back to
        # the bundle repo + a default preset so the driver has something to
        # warm-start from.
        if values.get("model") is None:
            if values.get("preset") is None:
                values["preset"] = LayaTrainerPreset.MULTILINGUAL
            values["model"] = {
                "provider": ModelProvider.HUGGINGFACE,
                "repository": _DEFAULT_MODEL_REPOSITORY,
            }
        return values
