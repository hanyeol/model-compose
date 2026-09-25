from typing import Literal, Optional, Union, List, Annotated, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import TypedDecisionModelActionConfig
from ..common import CommonTypedDecisionModelComponentConfig
from .common import TypedDecisionModelFamily
from ....common import ModelDriverType, ModelProvider, HuggingfaceModelConfig, LocalModelConfig

class LayaPreset(str, Enum):
    ENGLISH         = "english"
    MULTILINGUAL    = "multilingual"
    TYPED_DECISIONS = "typed-decisions"

# Convai Innovations ships all three checkpoints in a single bundle repo, one
# per subfolder; the driver uses the preset to pick which subfolder to load.
_BUNDLE_REPOSITORY = "convaiinnovations/laya"

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
    preset: LayaPreset = Field(default=LayaPreset.MULTILINGUAL, description="Laya checkpoint: 'english' (ModernBERT-large), 'multilingual' (mmBERT-base, 100+ languages), or 'typed-decisions' (fine-tuned on the typed-decisions workflows).")
    model: LayaTypedDecisionModelConfig = Field(..., description="Laya checkpoint — a HuggingFace repo ID or a local directory. Defaults to the bundle repo hosting all three presets.")
    max_seq_length: Optional[int] = Field(default=None, description="Per-call encoder token budget; overrides the checkpoint default.")
    max_head_length: Optional[int] = Field(default=None, description="Per-call per-question head token budget; overrides the checkpoint default.")
    fast: bool = Field(default=False, description="Enable the TileLang CUDA fast path (requires laya[fast]).")
    actions: List[TypedDecisionModelActionConfig] = Field(default_factory=list, description="Actions this typed decision component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model_from_preset(cls, values: Dict[str, Any]):
        # Fill in a default `model` config that points at the bundle repo when
        # the user hasn't specified one. The bundle hosts all three presets;
        # the driver reads `preset` to pick the right subfolder to snapshot.
        if values.get("model") is None:
            values["model"] = {
                "provider": ModelProvider.HUGGINGFACE,
                "repository": _BUNDLE_REPOSITORY,
            }
        return values
