from typing import Literal, List, Optional, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import PiH3ImageToVideoModelActionConfig
from mindor.dsl.utils.path import is_local_path
from ..common import CommonImageToVideoModelComponentConfig
from .common import ImageToVideoModelFamily
from ....common import ModelDriverType, ModelProvider, ModelSubmoduleConfig

_DEFAULT_MODEL_REPOSITORY = "multimodalart/MiniMax-H3-Pruned"
_DEFAULT_ADAPTER_REPOSITORY = "Lakonik/pi-H3"

class PiH3ImageToVideoModelComponentConfig(CommonImageToVideoModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageToVideoModelFamily.PI_H3]
    step_count: Literal[2, 4] = Field(default=4, description="Sampling step count baked into the distilled adapter (2 or 4).")
    dwd: bool = Field(default=True, description="Use the Decoding Without a Decoder adapter; disables the video VAE on the final step.")
    adapter_repository: str = Field(default=_DEFAULT_ADAPTER_REPOSITORY, description="Hugging Face repo hosting the pi-H3 adapters.")
    fp8_quantize: bool = Field(default=False, description="Apply LakonLab FP8 weight quantization to frozen linears.")
    cpu_offload: bool = Field(default=False, description="Offload submodules to CPU during generation to save VRAM.")
    text_encoder: Optional[ModelSubmoduleConfig] = Field(default=None, description="Overrides the pipeline's bundled Qwen3-VL text encoder.")
    actions: List[PiH3ImageToVideoModelActionConfig] = Field(default_factory=list, description="Actions this image-to-video component exposes to workflows.")

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
    def reject_peft_adapter(self):
        if self.peft_adapter:
            raise ValueError("pi-h3 does not support `peft_adapter`; the distilled adapter owns the LoRA slot.")
        return self
