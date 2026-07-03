from typing import Union
from pydantic import Field
from .common import CommonHuggingfaceTextToImageModelActionConfig, CommonHuggingfaceTextToImageParamsConfig

class FluxHuggingfaceTextToImageParamsConfig(CommonHuggingfaceTextToImageParamsConfig):
    num_inference_steps: Union[int, str] = Field(default=28, description="Number of denoising steps. Use 28 for FLUX.1-dev, 4 for FLUX.1-schnell.")
    guidance_scale: Union[float, str] = Field(default=3.5, description="Guidance scale. Use 3.5 for FLUX.1-dev, 0.0 for FLUX.1-schnell.")
    max_sequence_length: Union[int, str] = Field(default=512, description="Maximum sequence length for the T5 text encoder.")

class FluxHuggingfaceTextToImageModelActionConfig(CommonHuggingfaceTextToImageModelActionConfig):
    params: FluxHuggingfaceTextToImageParamsConfig = Field(default_factory=FluxHuggingfaceTextToImageParamsConfig, description="Image generation configuration parameters.")
