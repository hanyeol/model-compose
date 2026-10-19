from typing import Literal, List, Optional, Union, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from ..common import CommonMusicGenerationModelComponentConfig
from .common import MusicGenerationModelFamily
from ....common import ModelDriverType, ModelSubmoduleConfig, ModelQuantizationConfig, ModelQuantizationType, PeftAdapterType

_DEFAULT_VAE_MODEL_REPOSITORY = "m-a-p/YuE2-Vae"

class Yue2Backend(str, Enum):
    TORCH       = "torch"
    TORCH_EAGER = "torch-eager"
    VLLM        = "vllm"

class Yue2Submodule(str, Enum):
    AR  = "ar"
    VAE = "vae"

class Yue2QuantizationConfig(ModelQuantizationConfig):
    type: Literal[ModelQuantizationType.FP8] = Field(..., description="Quantization scheme applied to the YuE2 AR model; only fp8 is supported.")

    @model_validator(mode="after")
    def reject_unsupported_options(self):
        if self.compute_dtype is not None:
            raise ValueError("compute_dtype is only supported for 4-bit quantization, not fp8.")
        if not self.double_quant:
            raise ValueError("double_quant is only supported for 4-bit quantization, not fp8.")
        return self

class Yue2VaeConfig(ModelSubmoduleConfig):
    tile_size: Optional[Union[int, str]] = Field(default=None, description="VAE decode tile size in frames; defaults to 512 for <=12 GiB budgets and 1024 otherwise.")

class Yue2MusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicGenerationModelFamily.YUE2]
    vae: Yue2VaeConfig = Field(default_factory=lambda: Yue2VaeConfig(model=_DEFAULT_VAE_MODEL_REPOSITORY), description="VAE decoder used to render audio; defaults to the m-a-p/YuE2-Vae Hub repository.")
    nar: Optional[ModelSubmoduleConfig] = Field(default=None, description="NAR LoRA weights merged into the base pipeline; None uses the stock NAR shipped with the AR model.")
    backend: Yue2Backend = Field(default=Yue2Backend.TORCH, description="Inference backend for autoregressive generation (torch, torch-eager, vllm).")
    quantization: Optional[Yue2QuantizationConfig] = Field(default=None, description="Weight quantization applied to the AR model; None disables quantization.")
    memory_budget_gib: Union[float, str] = Field(default=24, description="GPU memory budget in GiB reserved for generation.")
    cpu_offload: Optional[Union[Yue2Submodule, List[Yue2Submodule]]] = Field(default=None, description="Submodules to run on CPU: 'ar' offloads the AR model during NAR synthesis, 'vae' runs VAE decode on CPU.")
    verify_hashes: Union[bool, str] = Field(default=True, description="Whether to verify model file checksums on load.")
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list, description="Actions this YuE2 music generation component exposes to workflows.")

    @model_validator(mode="before")
    def apply_default_vae(cls, values: Dict[str, Any]):
        if values.get("vae") is None:
            values["vae"] = { "model": _DEFAULT_VAE_MODEL_REPOSITORY }
        return values

    @model_validator(mode="after")
    def validate_lora_peft_adapter(self):
        for index, adapter in enumerate(self.peft_adapter or []):
            if adapter.type != PeftAdapterType.LORA:
                raise ValueError(
                    f"peft_adapter[{index}] has type={adapter.type.value!r}; "
                    f"yue2 music-generation only supports type={PeftAdapterType.LORA.value!r}."
                )
        return self
