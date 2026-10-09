from typing import Union, Optional, List
from pydantic import Field
from .common import CommonVideoToVideoParamsConfig, CommonVideoToVideoModelActionConfig

class AnimateDiffHuggingfaceVideoToVideoParamsConfig(CommonVideoToVideoParamsConfig):
    inference_steps: Union[int, str] = Field(default=25, description="Number of diffusion inference steps.")
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale applied during sampling.")
    denoise_strength: Union[float, str] = Field(default=0.5, description="Denoising strength; higher values follow the prompt more, lower values preserve the input video.")
    ip_adapter_scale: Union[float, str] = Field(default=0.6, description="IP-Adapter influence when a reference image is provided; 0 disables, 1 relies fully on the reference.")

class AnimateDiffHuggingfaceVideoToVideoModelActionConfig(CommonVideoToVideoModelActionConfig):
    conditioning_frames: Optional[Union[str, List[str]]] = Field(default=None, description="Per-ControlNet frame sequence(s) used as conditioning; one reference per ControlNet configured on the component.")
    controlnet_conditioning_scale: Union[float, List[float], str] = Field(default=1.0, description="Strength of each ControlNet's influence; scalar or per-ControlNet list.")
    control_guidance_start: Union[float, List[float], str] = Field(default=0.0, description="Fraction of total steps after which each ControlNet starts applying.")
    control_guidance_end: Union[float, List[float], str] = Field(default=1.0, description="Fraction of total steps after which each ControlNet stops applying.")
    params: AnimateDiffHuggingfaceVideoToVideoParamsConfig = Field(
        default_factory=AnimateDiffHuggingfaceVideoToVideoParamsConfig,
        description="AnimateDiff video-to-video generation parameters.",
    )

HuggingfaceVideoToVideoModelActionConfig = Union[
    AnimateDiffHuggingfaceVideoToVideoModelActionConfig,
]
