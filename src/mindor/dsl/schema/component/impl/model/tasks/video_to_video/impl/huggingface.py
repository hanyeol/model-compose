from typing import Literal, List, Optional, Union, Annotated
from enum import Enum
from pydantic import Field, model_validator
from typing import Dict, Any
from mindor.dsl.utils.path import is_local_path
from mindor.dsl.schema.action import AnimateDiffHuggingfaceVideoToVideoModelActionConfig
from .common import CommonVideoToVideoModelComponentConfig
from ...base.diffusion import DiffusionControlNetConfig, DiffusionCpuOffload, DiffusionIpAdapterConfig, DiffusionSchedulerConfig
from ...common import ModelDriverType, ModelConfig, ModelProvider

class HuggingfaceVideoToVideoModelArchitecture(str, Enum):
    ANIMATEDIFF = "animatediff"

class CommonHuggingfaceVideoToVideoModelComponentConfig(CommonVideoToVideoModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    scheduler: Optional[DiffusionSchedulerConfig] = Field(default=None, description="Overrides the pipeline's default scheduler; accepts an alias or `{ type, options }`.")
    cpu_offload: Optional[DiffusionCpuOffload] = Field(default=None, description="CPU offload strategy: 'model'/'sequential' for whole pipeline, or list of submodule names for selective offload.")
    vae_tiling: bool = Field(default=False, description="Decode the VAE in tiles to reduce VRAM on smaller GPUs, at the cost of possible seam artifacts at tile boundaries.")

class AnimateDiffHuggingfaceVideoToVideoModelComponentConfig(CommonHuggingfaceVideoToVideoModelComponentConfig):
    architecture: Literal[HuggingfaceVideoToVideoModelArchitecture.ANIMATEDIFF]
    motion_adapter: ModelConfig = Field(..., description="Motion adapter model applied on top of the base diffusion model.")
    ip_adapter: Optional[List[DiffusionIpAdapterConfig]] = Field(default=None, description="Optional IP-Adapter(s) used when actions supply a `reference_image`; accepts a single entry or a list for stacking multiple IP-Adapters.")
    controlnet: Optional[List[DiffusionControlNetConfig]] = Field(default=None, description="ControlNet models conditioning the diffusion pipeline; accepts a single entry or a list for stacking multiple ControlNets.")
    actions: List[AnimateDiffHuggingfaceVideoToVideoModelActionConfig] = Field(default_factory=list, description="Actions this video-to-video component exposes to workflows.")

    @model_validator(mode="before")
    def inflate_motion_adapter(cls, values: Dict[str, Any]):
        adapter = values.get("motion_adapter")
        if isinstance(adapter, str):
            if is_local_path(adapter):
                values["motion_adapter"] = { "provider": ModelProvider.LOCAL, "path": adapter }
            else:
                values["motion_adapter"] = { "provider": ModelProvider.HUGGINGFACE, "repository": adapter }

        adapter = values.get("motion_adapter")
        if isinstance(adapter, dict) and "provider" not in adapter:
            if "repository" in adapter:
                adapter["provider"] = ModelProvider.HUGGINGFACE
            elif "name" in adapter:
                adapter["provider"] = ModelProvider.NAMED
            else:
                adapter["provider"] = ModelProvider.LOCAL

        return values

    @model_validator(mode="before")
    def normalize_ip_adapter(cls, values: Dict[str, Any]):
        ip_adapter = values.get("ip_adapter", None)
        if ip_adapter is not None and not isinstance(ip_adapter, list):
            values["ip_adapter"] = [ ip_adapter ]
        return values

    @model_validator(mode="before")
    def normalize_controlnet(cls, values: Dict[str, Any]):
        controlnet = values.get("controlnet", None)
        if controlnet is not None:
            controlnets = []
            if not isinstance(controlnet, list):
                controlnet = [ controlnet ]
            for value in controlnet:
                if isinstance(value, str):
                    controlnets.append({ "model": value })
                else:
                    controlnets.append(value)
            values["controlnet"] = controlnets
        return values

HuggingfaceVideoToVideoModelComponentConfig = Annotated[
    Union[
        AnimateDiffHuggingfaceVideoToVideoModelComponentConfig,
    ],
    Field(discriminator="architecture"),
]
