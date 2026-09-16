from typing import Union
from pydantic import Field
from .common import CommonVideoToVideoParamsConfig, CommonVideoToVideoModelActionConfig

class AnimateDiffHuggingfaceVideoToVideoParamsConfig(CommonVideoToVideoParamsConfig):
    inference_steps: Union[int, str] = Field(default=25, description="Number of diffusion inference steps.")
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale applied during sampling.")
    denoise_strength: Union[float, str] = Field(default=0.5, description="Denoising strength; higher values follow the prompt more, lower values preserve the input video.")

class AnimateDiffHuggingfaceVideoToVideoModelActionConfig(CommonVideoToVideoModelActionConfig):
    params: AnimateDiffHuggingfaceVideoToVideoParamsConfig = Field(
        default_factory=AnimateDiffHuggingfaceVideoToVideoParamsConfig,
        description="AnimateDiff video-to-video generation parameters.",
    )

HuggingfaceVideoToVideoModelActionConfig = Union[
    AnimateDiffHuggingfaceVideoToVideoModelActionConfig,
]
