from typing import Literal, List, Optional, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import TextToVideoModelActionConfig
from ..common import CommonTextToVideoModelComponentConfig
from .common import TextToVideoModelFamily
from ....common import ModelDriverType, ModelProvider, ModelSubmoduleConfig

_DEFAULT_MODEL_REPOSITORY = "MiniMaxAI/MiniMax-H3"

class MinimaxH3Backend(str, Enum):
    TORCH = "torch"
    SOL   = "sol"

class MinimaxH3TextToVideoModelComponentConfig(CommonTextToVideoModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TextToVideoModelFamily.MINIMAX_H3]
    backend: MinimaxH3Backend = Field(default=MinimaxH3Backend.TORCH, description="Attention backend for the main transformer blocks.")
    cpu_offload: bool = Field(default=False, description="Offload submodules to CPU during generation to save VRAM.")
    text_encoder: Optional[ModelSubmoduleConfig] = Field(default=None, description="Overrides the pipeline's bundled Qwen3-VL text encoder; set this to swap in a different checkpoint (e.g. quantized or fine-tuned).")
    actions: List[TextToVideoModelActionConfig] = Field(default_factory=list, description="Actions this text-to-video component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": _DEFAULT_MODEL_REPOSITORY }
        return values
