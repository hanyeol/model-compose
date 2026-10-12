from typing import Literal, Union, Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.utils.path import is_local_path
from ..common import ModelConfig, ModelProvider, ModelPrecision

class DiffusionSubmodule(str, Enum):
    TEXT_ENCODER   = "text_encoder"
    TEXT_ENCODER_2 = "text_encoder_2"
    TEXT_ENCODER_3 = "text_encoder_3"
    TRANSFORMER    = "transformer"
    UNET           = "unet"
    VAE            = "vae"
    IMAGE_ENCODER  = "image_encoder"

class DiffusionSchedulerType(str, Enum):
    DDIM                 = "ddim"
    DDPM                 = "ddpm"
    EULER                = "euler"
    EULER_KARRAS         = "euler_karras"
    EULER_A              = "euler_a"
    HEUN                 = "heun"
    LMS                  = "lms"
    LMS_KARRAS           = "lms_karras"
    DPM_2                = "dpm_2"
    DPM_2_KARRAS         = "dpm_2_karras"
    DPM_2_A              = "dpm_2_a"
    DPM_2_A_KARRAS       = "dpm_2_a_karras"
    DPMPP_2M             = "dpmpp_2m"
    DPMPP_2M_KARRAS      = "dpmpp_2m_karras"
    DPMPP_2M_SDE         = "dpmpp_2m_sde"
    DPMPP_2M_SDE_KARRAS  = "dpmpp_2m_sde_karras"
    DPMPP_SDE            = "dpmpp_sde"
    DPMPP_SDE_KARRAS     = "dpmpp_sde_karras"
    UNIPC                = "unipc"
    PNDM                 = "pndm"
    DEIS                 = "deis"
    LCM                  = "lcm"

DiffusionCpuOffload = Union[Literal[ "model", "sequential" ], List[DiffusionSubmodule]]

class DiffusionVaeConfig(BaseModel):
    model: ModelConfig = Field(..., description="VAE model identifier — a HuggingFace repo ID or a local path.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numeric precision used for VAE weights and computation.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Whether to load the VAE with reduced CPU RAM usage.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }

        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            if "repository" in model:
                model["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in model:
                model["provider"] = ModelProvider.NAMED
            else:
                model["provider"] = ModelProvider.LOCAL

        return values

class DiffusionControlNetConfig(BaseModel):
    model: ModelConfig = Field(..., description="ControlNet model identifier — a HuggingFace repo ID or a local path.")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numeric precision used for ControlNet weights and computation.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Whether to load the ControlNet with reduced CPU RAM usage.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Dict[str, Any]):
        model = values.get("model")
        if isinstance(model, str):
            if is_local_path(model):
                values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
            else:
                values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }

        model = values.get("model")
        if isinstance(model, dict) and "provider" not in model:
            if "repository" in model:
                model["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in model:
                model["provider"] = ModelProvider.NAMED
            else:
                model["provider"] = ModelProvider.LOCAL

        return values

class DiffusionImageEncoderConfig(BaseModel):
    model: ModelConfig = Field(..., description="CLIP image encoder identifier — a HuggingFace repo ID or a local path. Required when the IP-Adapter variant doesn't match the default ViT-H encoder (e.g. `ip-adapter_sd15_vit-G` needs ViT-G).")
    precision: Optional[ModelPrecision] = Field(default=None, description="Numeric precision used for image encoder weights and computation.")
    low_cpu_mem_usage: Union[bool, str] = Field(default=False, description="Whether to load the image encoder with reduced CPU RAM usage.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Any):
        if isinstance(values, str):
            if is_local_path(values):
                return { "model": { "provider": ModelProvider.LOCAL, "path": values } }
            return { "model": { "provider": ModelProvider.HUGGINGFACE, "repository": values } }

        if isinstance(values, dict):
            model = values.get("model")
            if isinstance(model, str):
                if is_local_path(model):
                    values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
                else:
                    values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }

            model = values.get("model")
            if isinstance(model, dict) and "provider" not in model:
                if "repository" in model:
                    model["provider"] = ModelProvider.HUGGINGFACE
                elif "name" in model:
                    model["provider"] = ModelProvider.NAMED
                else:
                    model["provider"] = ModelProvider.LOCAL

        return values

class DiffusionIpAdapterConfig(BaseModel):
    model: ModelConfig = Field(..., description="IP-Adapter model identifier — a HuggingFace repo ID or a local path.")
    filename: Optional[str] = Field(default=None, description="Weight file inside the IP-Adapter repo as `<subfolder>/<weight_name>` (e.g. `models/ip-adapter_sd15.bin`).")
    image_encoder: Optional[DiffusionImageEncoderConfig] = Field(default=None, description="Overrides the IP-Adapter's bundled CLIP image encoder; set this when the adapter variant requires a different encoder than the default ViT-H.")

    @model_validator(mode="before")
    def inflate_model(cls, values: Any):
        # Accept `ip_adapter: <repo>` shorthand and `ip_adapter: { <ModelConfig fields> }`
        # that pre-dates this config, in addition to the full
        # `ip_adapter: { model, filename, image_encoder }` block.
        if isinstance(values, str):
            if is_local_path(values):
                return { "model": { "provider": ModelProvider.LOCAL, "path": values } }
            return { "model": { "provider": ModelProvider.HUGGINGFACE, "repository": values } }

        if isinstance(values, dict) and "model" not in values:
            model_keys = { "provider", "repository", "path", "name", "revision" }
            if any(key in values for key in model_keys):
                carried: Dict[str, Any] = {}
                if "filename" in values:
                    carried["filename"] = values.pop("filename")
                values = { **carried, "model": values }

        if isinstance(values, dict):
            model = values.get("model")
            if isinstance(model, str):
                if is_local_path(model):
                    values["model"] = { "provider": ModelProvider.LOCAL, "path": model }
                else:
                    values["model"] = { "provider": ModelProvider.HUGGINGFACE, "repository": model }

            model = values.get("model")
            if isinstance(model, dict) and "provider" not in model:
                if "repository" in model:
                    model["provider"] = ModelProvider.HUGGINGFACE
                elif "name" in model:
                    model["provider"] = ModelProvider.NAMED
                else:
                    model["provider"] = ModelProvider.LOCAL

        return values

class DiffusionSchedulerConfig(BaseModel):
    type: DiffusionSchedulerType = Field(..., description="Scheduler alias (ComfyUI/A1111 style) resolved to a diffusers class and preset kwargs.")
    options: Dict[str, Any] = Field(default_factory=dict, description="Extra kwargs forwarded to `SchedulerClass.from_config` (e.g. `beta_schedule`, `timestep_spacing`, `prediction_type`).")

    @model_validator(mode="before")
    def inflate_type(cls, values: Any):
        if isinstance(values, str):
            return { "type": values }
        return values
