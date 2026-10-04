from typing import Literal, Optional, Union, List, Annotated, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import TypedDecisionModelActionConfig
from ..common import CommonTypedDecisionModelComponentConfig
from .common import TypedDecisionModelFamily
from ....common import ModelDriverType, ModelProvider, HuggingfaceModelConfig, LocalModelConfig

# Convai Innovations ships all three checkpoints in a single repo, one per
# subfolder. Used as the fallback when the user provides neither `model` nor
# `preset`; the driver reads `preset` to pick which subfolder to load.
_DEFAULT_REPOSITORY = "convaiinnovations/laya"

class LayaPreset(str, Enum):
    ENGLISH         = "english"
    MULTILINGUAL    = "multilingual"
    TYPED_DECISIONS = "typed-decisions"

LayaTypedDecisionModelConfig = Annotated[
    Union[
        HuggingfaceModelConfig,
        LocalModelConfig,
    ],
    Field(discriminator="provider")
]

class LayaTypedDecisionModelComponentConfig(CommonTypedDecisionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TypedDecisionModelFamily.LAYA]
    model: LayaTypedDecisionModelConfig = Field(..., description="Laya checkpoint — a HuggingFace repo ID or a local directory. Defaults to the bundle repo hosting all three presets.")
    preset: Optional[LayaPreset] = Field(default=None, description="Laya checkpoint: 'english' (ModernBERT-large), 'multilingual' (mmBERT-base, 100+ languages), or 'typed-decisions' (fine-tuned on the typed-decisions workflows).")
    max_seq_length: Optional[int] = Field(default=None, description="Per-call encoder token budget; overrides the checkpoint default.")
    max_head_length: Optional[int] = Field(default=None, description="Per-call per-question head token budget; overrides the checkpoint default.")
    fast: bool = Field(default=False, description="Enable the TileLang CUDA fast path (requires laya[fast]).")
    actions: List[TypedDecisionModelActionConfig] = Field(default_factory=list, description="Actions this typed decision component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model_from_preset(cls, values: Dict[str, Any]):
        # When the user supplies their own `model`, trust it as-is and leave
        # `preset` untouched. Only when neither is given do we fall back to
        # the bundle repo + a default preset so the driver has something to
        # snapshot.
        if values.get("model") is None:
            if values.get("preset") is None:
                values["preset"] = LayaPreset.MULTILINGUAL
            values["model"] = {
                "provider": ModelProvider.HUGGINGFACE,
                "repository": _DEFAULT_REPOSITORY,
            }
        return values
