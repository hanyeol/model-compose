from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import LdsrImageUpscalingModelActionConfig
from ..common import CommonImageUpscalingModelComponentConfig
from .common import ImageUpscalingModelFamily
from ....base.diffusion import DiffusionCpuOffload, DiffusionSchedulerConfig
from ....common import ModelDriverType

class LdsrImageUpscalingModelComponentConfig(CommonImageUpscalingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageUpscalingModelFamily.LDSR]
    scheduler: Optional[DiffusionSchedulerConfig] = Field(default=None, description="Overrides the pipeline's default scheduler; accepts an alias or `{ type, options }`.")
    cpu_offload: Optional[DiffusionCpuOffload] = Field(default=None, description="CPU offload strategy: 'model'/'sequential' for whole pipeline, or list of submodule names for selective offload.")
    vae_tiling: bool = Field(default=False, description="Decode the VAE in tiles to reduce VRAM on smaller GPUs, at the cost of possible seam artifacts at tile boundaries.")
    actions: List[LdsrImageUpscalingModelActionConfig] = Field(default_factory=list, description="Actions this image upscaling component exposes to workflows.")
