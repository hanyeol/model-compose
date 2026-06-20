from typing import Literal, Union, Optional, Annotated
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonImageGenerationModelActionConfig

class HuggingfaceImageGenerationModelArchitecture(str, Enum):
    SDXL          = "sdxl"
    FLUX          = "flux"
    HUNYUAN_IMAGE = "hunyuan-image"

class SdxlHuggingfaceImageGenerationParamsConfig(BaseModel):
    negative_prompt: Optional[Union[str, list]] = Field(default=None, description="Negative prompt(s) describing what to avoid.")
    num_inference_steps: Union[int, str] = Field(default=30, description="Number of denoising steps.")
    guidance_scale: Union[float, str] = Field(default=7.5, description="Classifier-free guidance scale.")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class SdxlHuggingfaceImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.SDXL]
    params: SdxlHuggingfaceImageGenerationParamsConfig = Field(default_factory=SdxlHuggingfaceImageGenerationParamsConfig, description="Image generation configuration parameters.")

class FluxHuggingfaceImageGenerationParamsConfig(BaseModel):
    num_inference_steps: Union[int, str] = Field(default=28, description="Number of denoising steps. Use 28 for FLUX.1-dev, 4 for FLUX.1-schnell.")
    guidance_scale: Union[float, str] = Field(default=3.5, description="Guidance scale. Use 3.5 for FLUX.1-dev, 0.0 for FLUX.1-schnell.")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    max_sequence_length: Union[int, str] = Field(default=512, description="Maximum sequence length for the T5 text encoder.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class FluxHuggingfaceImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.FLUX]
    params: FluxHuggingfaceImageGenerationParamsConfig = Field(default_factory=FluxHuggingfaceImageGenerationParamsConfig, description="Image generation configuration parameters.")

class HunyuanImageHuggingfaceImageGenerationParamsConfig(BaseModel):
    negative_prompt: Optional[Union[str, list]] = Field(default=None, description="Negative prompt(s) describing what to avoid.")
    num_inference_steps: Union[int, str] = Field(default=50, description="Number of denoising steps.")
    distilled_guidance_scale: Union[float, str] = Field(default=3.25, description="Distilled guidance scale (Hunyuan-Image uses adaptive projected mix guidance).")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class HunyuanImageHuggingfaceImageGenerationModelActionConfig(CommonImageGenerationModelActionConfig):
    architecture: Literal[HuggingfaceImageGenerationModelArchitecture.HUNYUAN_IMAGE]
    params: HunyuanImageHuggingfaceImageGenerationParamsConfig = Field(default_factory=HunyuanImageHuggingfaceImageGenerationParamsConfig, description="Image generation configuration parameters.")

HuggingfaceImageGenerationModelActionConfig = Annotated[
    Union[
        SdxlHuggingfaceImageGenerationModelActionConfig,
        FluxHuggingfaceImageGenerationModelActionConfig,
        HunyuanImageHuggingfaceImageGenerationModelActionConfig,
    ],
    Field(discriminator="architecture")
]
