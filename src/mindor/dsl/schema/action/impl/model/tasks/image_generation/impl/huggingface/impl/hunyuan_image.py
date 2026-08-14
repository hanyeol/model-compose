from typing import Union, Literal, Optional, Annotated
from pydantic import Field
from ...common import ImageGenerationActionMethod
from .common import CommonHuggingfaceImageGenerationModelActionConfig, CommonHuggingfaceImageGenerationParamsConfig

class HunyuanImageHuggingfaceImageGenerationParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    num_inference_steps: Union[int, str] = Field(default=50, description="Number of denoising steps run during sampling.")
    distilled_guidance_scale: Union[float, str] = Field(default=3.25, description="Distilled guidance scale used by Hunyuan-Image's adaptive projected mix guidance.")

class HunyuanImageHuggingfaceImageGenerationGenerateModelActionConfig(CommonHuggingfaceImageGenerationModelActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    params: HunyuanImageHuggingfaceImageGenerationParamsConfig = Field(default_factory=HunyuanImageHuggingfaceImageGenerationParamsConfig, description="Hunyuan-Image-specific generation parameters.")

HunyuanImageHuggingfaceImageGenerationModelActionConfig = Annotated[
    Union[
        HunyuanImageHuggingfaceImageGenerationGenerateModelActionConfig,
    ],
    Field(discriminator="method")
]
