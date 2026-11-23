from typing import Literal, List, Optional, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import MinimaxH3ImageGenerationModelActionConfig
from mindor.dsl.utils.path import is_local_path
from ..common import CommonImageGenerationModelComponentConfig
from .common import ImageGenerationModelFamily
from ....common import ModelDriverType, ModelProvider, ModelSubmoduleConfig, PeftAdapterType

class MinimaxH3ImageGenerationBackend(str, Enum):
    TORCH = "torch"
    SOL   = "sol"

_DEFAULT_MODEL_REPOSITORY = "MiniMaxAI/MiniMax-H3-Image"

class MinimaxH3ImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageGenerationModelFamily.MINIMAX_H3]
    backend: MinimaxH3ImageGenerationBackend = Field(default=MinimaxH3ImageGenerationBackend.TORCH, description="Attention backend for the main transformer blocks.")
    cpu_offload: bool = Field(default=False, description="Offload submodules to CPU during generation to save VRAM.")
    text_encoder: Optional[ModelSubmoduleConfig] = Field(default=None, description="Overrides the pipeline's bundled Qwen3-VL text encoder; set this to swap in a different checkpoint (e.g. quantized or fine-tuned).")
    actions: List[MinimaxH3ImageGenerationModelActionConfig] = Field(default_factory=list, description="Actions this image generation component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if model is None:
            model = _DEFAULT_MODEL_REPOSITORY
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }
        return values

    @model_validator(mode="after")
    def validate_lora_peft_adapter(self):
        for index, adapter in enumerate(self.peft_adapter or []):
            if adapter.type != PeftAdapterType.LORA:
                raise ValueError(
                    f"peft_adapter[{index}] has type={adapter.type.value!r}; "
                    f"minimax-h3 only supports type={PeftAdapterType.LORA.value!r}."
                )
        return self
