from typing import Union, Optional, List, Any
from pydantic import BaseModel, Field
from ...common import CommonImageGenerationModelActionConfig, CommonImageGenerationModelInpaintActionConfig

class CommonHuggingfaceImageGenerationParamsConfig(BaseModel):
    inference_steps: Union[int, str] = Field(default=30, description="Number of denoising steps run during sampling.")
    sigmas: Optional[Union[List[float], str]] = Field(default=None, description="Custom sigma schedule (list of floats) that bypasses the pipeline scheduler; used by distilled/accelerator LoRAs.")
    controlnet_conditioning_scale: Union[float, List[float], str] = Field(default=1.0, description="Strength of each ControlNet's influence; scalar or per-ControlNet list.")
    control_guidance_start: Union[float, List[float], str] = Field(default=0.0, description="Fraction of total steps after which each ControlNet starts applying.")
    control_guidance_end: Union[float, List[float], str] = Field(default=1.0, description="Fraction of total steps after which each ControlNet stops applying.")

class CommonHuggingfaceImageGenerationInpaintParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    denoise_strength: Union[float, str] = Field(default=1.0, description="Noise strength applied to the input image before denoising.")

class CommonHuggingfaceImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    control_image: Optional[Union[Any, List[Any], List[List[Any]], str]] = Field(default=None, description="Control image(s) fed to ControlNet; a single image (one ControlNet), a list of images (one per ControlNet), or a per-input list of such lists for batched inputs.")
    params: CommonHuggingfaceImageGenerationParamsConfig = Field(default_factory=CommonHuggingfaceImageGenerationParamsConfig, description="Sampling parameters used for image generation.")

class CommonHuggingfaceImageGenerationModelInpaintActionConfig(CommonImageGenerationModelInpaintActionConfig):
    control_image: Optional[Union[Any, List[Any], List[List[Any]], str]] = Field(default=None, description="Control image(s) fed to ControlNet; a single image (one ControlNet), a list of images (one per ControlNet), or a per-input list of such lists for batched inputs.")
    params: CommonHuggingfaceImageGenerationInpaintParamsConfig = Field(default_factory=CommonHuggingfaceImageGenerationInpaintParamsConfig, description="Sampling parameters used for image inpainting.")
