from typing import Union, Literal, Tuple, Annotated
from pydantic import Field
from ...common import ImageGenerationActionMethod
from .common import (
    CommonHuggingfaceImageGenerationModelGenerateActionConfig,
    CommonHuggingfaceImageGenerationModelInpaintActionConfig,
    CommonHuggingfaceImageGenerationParamsConfig,
    CommonHuggingfaceImageGenerationInpaintParamsConfig,
)

class Flux2HuggingfaceImageGenerationParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    inference_steps: Union[int, str] = Field(default=50, description="Number of denoising steps run during sampling.")
    guidance_scale: Union[float, str] = Field(default=4.0, description="Classifier-free guidance scale.")
    max_sequence_length: Union[int, str] = Field(default=512, description="Maximum token sequence length for the text encoder.")
    text_encoder_out_layers: Union[Tuple[int, int, int], str] = Field(default=(10, 20, 30), description="Hidden layer indices tapped from the text encoder.")

class Flux2KleinHuggingfaceImageGenerationParamsConfig(CommonHuggingfaceImageGenerationParamsConfig):
    inference_steps: Union[int, str] = Field(default=50, description="Number of denoising steps run during sampling.")
    guidance_scale: Union[float, str] = Field(default=4.0, description="Classifier-free guidance scale.")
    max_sequence_length: Union[int, str] = Field(default=512, description="Maximum token sequence length for the text encoder.")
    text_encoder_out_layers: Union[Tuple[int, int, int], str] = Field(default=(9, 18, 27), description="Hidden layer indices tapped from the text encoder.")

class Flux2KleinHuggingfaceImageGenerationInpaintParamsConfig(CommonHuggingfaceImageGenerationInpaintParamsConfig):
    inference_steps: Union[int, str] = Field(default=50, description="Number of denoising steps run during sampling.")
    guidance_scale: Union[float, str] = Field(default=8.0, description="Classifier-free guidance scale.")
    max_sequence_length: Union[int, str] = Field(default=512, description="Maximum token sequence length for the text encoder.")
    text_encoder_out_layers: Union[Tuple[int, int, int], str] = Field(default=(9, 18, 27), description="Hidden layer indices tapped from the text encoder.")
    denoise_strength: Union[float, str] = Field(default=0.8, description="Noise strength applied to the input image before denoising.")

class Flux2HuggingfaceImageGenerationModelGenerateActionConfig(CommonHuggingfaceImageGenerationModelGenerateActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    params: Flux2HuggingfaceImageGenerationParamsConfig = Field(default_factory=Flux2HuggingfaceImageGenerationParamsConfig, description="FLUX.2-specific image generation parameters.")

class Flux2KleinHuggingfaceImageGenerationModelGenerateActionConfig(CommonHuggingfaceImageGenerationModelGenerateActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    params: Flux2KleinHuggingfaceImageGenerationParamsConfig = Field(default_factory=Flux2KleinHuggingfaceImageGenerationParamsConfig, description="FLUX.2 Klein-specific image generation parameters.")

class Flux2KleinHuggingfaceImageGenerationModelInpaintActionConfig(CommonHuggingfaceImageGenerationModelInpaintActionConfig):
    method: Literal[ImageGenerationActionMethod.INPAINT] = Field(default=ImageGenerationActionMethod.INPAINT)
    params: Flux2KleinHuggingfaceImageGenerationInpaintParamsConfig = Field(default_factory=Flux2KleinHuggingfaceImageGenerationInpaintParamsConfig, description="FLUX.2 Klein-specific inpainting parameters.")

Flux2HuggingfaceImageGenerationModelActionConfig = Annotated[
    Flux2HuggingfaceImageGenerationModelGenerateActionConfig,
    Field(discriminator="method")
]

Flux2KleinHuggingfaceImageGenerationModelActionConfig = Annotated[
    Union[
        Flux2KleinHuggingfaceImageGenerationModelGenerateActionConfig,
        Flux2KleinHuggingfaceImageGenerationModelInpaintActionConfig,
    ],
    Field(discriminator="method")
]
