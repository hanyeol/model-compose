from typing import Literal, List, Optional, Union, Dict, Any
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from ..common import CommonMusicGenerationModelComponentConfig
from .common import MusicGenerationModelFamily
from ....common import ModelDriverType, ModelSubmoduleConfig, ModelQuantizationConfig, ModelQuantizationType

class Yue2Backend(str, Enum):
    TORCH       = "torch"
    TORCH_EAGER = "torch-eager"
    VLLM        = "vllm"

class Yue2Submodule(str, Enum):
    AR  = "ar"
    NAR = "nar"
    VAE = "vae"

_DEFAULT_VAE_MODEL_REPOSITORY = "m-a-p/YuE2-Vae"

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

class Yue2ArAdapterConfig(ModelSubmoduleConfig):
    weight: Union[float, str] = Field(default=1.0, description="Merge scale applied to the AR LoRA delta (W += weight · B @ A).")

class Yue2MusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicGenerationModelFamily.YUE2]
    vae: Yue2VaeConfig = Field(default_factory=lambda: Yue2VaeConfig(model=_DEFAULT_VAE_MODEL_REPOSITORY), description="VAE decoder used to render audio; defaults to the m-a-p/YuE2-Vae Hub repository.")
    ar_adapter: Optional[List[Yue2ArAdapterConfig]] = Field(default=None, description="AR LoRA adapter(s) merged into the AR path; accepts a single entry or a list for stacking.")
    nar_adapter: Optional[ModelSubmoduleConfig] = Field(default=None, description="Optional LoRA + I/O projection patch applied to the NAR path; None keeps the stock NAR that ships inside the AR checkpoint.")
    backend: Yue2Backend = Field(default=Yue2Backend.TORCH, description="Inference backend for autoregressive generation (torch, torch-eager, vllm).")
    quantization: Optional[Yue2QuantizationConfig] = Field(default=None, description="Weight quantization applied to the AR model; None disables quantization.")
    cpu_offload: Optional[Union[Yue2Submodule, List[Yue2Submodule]]] = Field(default=None, description="Submodules to run on CPU to reduce VRAM.")
    low_vram: Union[bool, str] = Field(default=False, description="Swap AR/NAR between GPU and CPU per chunk to minimize VRAM.")
    memory_budget: Union[float, str] = Field(default=24, description="GPU memory budget in GiB reserved for generation.")
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list, description="Actions this YuE2 music generation component exposes to workflows.")

    @model_validator(mode="before")
    def apply_default_vae(cls, values: Dict[str, Any]):
        if values.get("vae") is None:
            values["vae"] = { "model": _DEFAULT_VAE_MODEL_REPOSITORY }
        return values

    @model_validator(mode="before")
    def normalize_ar_adapter(cls, values: Dict[str, Any]):
        ar_adapter = values.get("ar_adapter", None)
        if ar_adapter is not None and not isinstance(ar_adapter, list):
            values["ar_adapter"] = [ ar_adapter ]
        return values

    @model_validator(mode="before")
    def normalize_cpu_offload(cls, values: Dict[str, Any]):
        cpu_offload = values.get("cpu_offload", None)
        if cpu_offload is not None and not isinstance(cpu_offload, list):
            values["cpu_offload"] = [ cpu_offload ]
        return values

    @model_validator(mode="after")
    def validate_cpu_offload(self):
        if Yue2Submodule.NAR in (self.cpu_offload or []):
            raise ValueError("cpu_offload='nar' is not supported; use 'low_vram' to swap AR/NAR per chunk.")
        if bool(self.low_vram) and Yue2Submodule.AR in (self.cpu_offload or []):
            raise ValueError("'low_vram' and cpu_offload='ar' both manage AR residency; enable only one.")
        if bool(self.low_vram) and self.backend == Yue2Backend.VLLM:
            raise ValueError("'low_vram' is not supported with backend='vllm'.")
        return self
