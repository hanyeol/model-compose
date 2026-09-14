from typing import Literal, List, Optional, Union, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from ..common import CommonMusicGenerationModelComponentConfig
from .common import MusicGenerationModelFamily
from ....common import ModelDriver, ModelConfig, ModelProvider, ModelQuantizationConfig, ModelQuantizationType

_DEFAULT_YUE2_VAE_REPOSITORY = "m-a-p/YuE2-Vae"

class Yue2Backend(str, Enum):
    TORCH       = "torch"
    TORCH_EAGER = "torch-eager"
    VLLM        = "vllm"

class Yue2QuantizationConfig(ModelQuantizationConfig):
    type: Literal[ModelQuantizationType.FP8] = Field(..., description="Quantization scheme applied to the YuE2 AR model; only fp8 is supported.")

    @model_validator(mode="after")
    def reject_unsupported_options(self):
        if self.compute_dtype is not None:
            raise ValueError("compute_dtype is only supported for 4-bit quantization, not fp8.")
        if not self.double_quant:
            raise ValueError("double_quant is only supported for 4-bit quantization, not fp8.")
        return self

class Yue2VaeConfig(BaseModel):
    model: ModelConfig = Field(..., description="VAE model identifier — a HuggingFace repo ID or a local path.")
    tile_size: Optional[Union[int, str]] = Field(default=None, description="VAE decode tile size in frames; defaults to 512 for <=12 GiB budgets and 1024 otherwise.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }
        return values

    @model_validator(mode="before")
    def fill_missing_model_provider(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            if "repository" in model:
                model["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in model:
                model["provider"] = ModelProvider.NAMED
            else:
                model["provider"] = ModelProvider.LOCAL
        return values

class Yue2MusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicGenerationModelFamily.YUE2]
    vae: Yue2VaeConfig = Field(default_factory=lambda: Yue2VaeConfig(model=_DEFAULT_YUE2_VAE_REPOSITORY), description="VAE decoder used to render audio; defaults to the m-a-p/YuE2-Vae Hub repository.")
    backend: Yue2Backend = Field(default=Yue2Backend.TORCH, description="Inference backend for autoregressive generation (torch, torch-eager, vllm).")
    quantization: Optional[Yue2QuantizationConfig] = Field(default=None, description="Weight quantization applied to the AR model; None disables quantization.")
    memory_budget_gib: Union[float, str] = Field(default=24, description="GPU memory budget in GiB reserved for generation.")
    offload_ar: Union[bool, str] = Field(default=False, description="Whether to offload the AR model to CPU during NAR synthesis to free GPU memory.")
    verify_hashes: Union[bool, str] = Field(default=True, description="Whether to verify model file checksums on load.")
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list, description="Actions this YuE2 music generation component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_vae(cls, values: Dict[str, Any]):
        vae = values.get("vae")
        if vae is None:
            values["vae"] = { "model": _DEFAULT_YUE2_VAE_REPOSITORY }
        elif isinstance(vae, str):
            values["vae"] = { "model": vae }
        return values
