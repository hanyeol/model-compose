from typing import Literal, Union, Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ..common import ModelSubmoduleConfig

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

class DiffusionIpAdapterConfig(ModelSubmoduleConfig):
    image_encoder: Optional[ModelSubmoduleConfig] = Field(default=None, description="Overrides the IP-Adapter's bundled CLIP image encoder; set this when the adapter variant requires a different encoder than the default ViT-H.")

class DiffusionSchedulerConfig(BaseModel):
    type: Optional[DiffusionSchedulerType] = Field(default=None, description="Scheduler alias (ComfyUI/A1111 style) resolved to a diffusers class and preset kwargs; omit to reconfigure the pipeline's existing scheduler class with `options` only.")
    options: Dict[str, Any] = Field(default_factory=dict, description="Extra kwargs forwarded to `SchedulerClass.from_config` (e.g. `beta_schedule`, `timestep_spacing`, `prediction_type`).")

    @model_validator(mode="before")
    def inflate_type(cls, values: Any):
        if isinstance(values, str):
            return { "type": values }
        return values
