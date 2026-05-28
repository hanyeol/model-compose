from typing import Union, Optional
from pydantic import Field
from ...common import CommonMusicGenerationParamsConfig, CommonMusicGenerationModelActionConfig

class AceStepMusicGenerationParamsConfig(CommonMusicGenerationParamsConfig):
    time_signature: Optional[Union[str, str]] = Field(default="4/4", description="Time signature (e.g. '4/4', '3/4').")
    inference_steps: Union[int, str] = Field(default=8, description="Number of diffusion inference steps. Turbo: 8, base: 32, sft: 50.")
    guidance_scale: Union[float, str] = Field(default=5.0, description="Classifier-free guidance scale.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for reproducibility.")

class AceStepMusicGenerationModelActionConfig(CommonMusicGenerationModelActionConfig):
    params: AceStepMusicGenerationParamsConfig = Field(default_factory=AceStepMusicGenerationParamsConfig, description="ACE-Step music generation parameters.")
