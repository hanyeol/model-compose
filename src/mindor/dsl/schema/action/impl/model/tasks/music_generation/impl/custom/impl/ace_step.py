from typing import Union, Optional
from pydantic import Field
from ...common import CommonMusicGenerationParamsConfig, CommonMusicGenerationModelActionConfig

class AceStepMusicGenerationParamsConfig(CommonMusicGenerationParamsConfig):
    time_signature: Optional[str] = Field(default="4/4", description="Musical time signature of the generated music (e.g., 4/4, 3/4).")
    inference_steps: Union[int, str] = Field(default=8, description="Number of diffusion inference steps (turbo: 8, base: 32, sft: 50).")
    guidance_scale: Union[float, str] = Field(default=5.0, description="Classifier-free guidance scale applied during sampling.")

class AceStepMusicGenerationModelActionConfig(CommonMusicGenerationModelActionConfig):
    params: AceStepMusicGenerationParamsConfig = Field(default_factory=AceStepMusicGenerationParamsConfig, description="ACE-Step music generation parameters.")
