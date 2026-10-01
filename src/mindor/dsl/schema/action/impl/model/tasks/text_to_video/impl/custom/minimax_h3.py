from typing import Union, Literal, Optional
from pydantic import BaseModel, Field
from ..common import CommonTextToVideoParamsConfig, CommonTextToVideoModelActionConfig

class MinimaxH3SolAttnConfig(BaseModel):
    tau: Union[float, str] = Field(default=1.0, description="Sol-Attn routing threshold scale (τ); higher skips more KV blocks.")
    thresh_type: Union[Literal["diag", "exact"], str] = Field(default="diag", description="Threshold estimation mode.")
    dense_steps: Optional[Union[int, str]] = Field(default=None, description="Run the last N denoising steps fully dense.")
    step_off: Optional[Union[float, str]] = Field(default=None, description="Dense fraction at the tail of the schedule.")

class MinimaxH3TextToVideoParamsConfig(CommonTextToVideoParamsConfig):
    inference_steps: Union[int, str] = Field(default=50, description="Number of sigma grid points (including the terminal 0), one less than the model evaluations.")
    sol_attn: Optional[MinimaxH3SolAttnConfig] = Field(default=None, description="Sol-Attn sparse attention acceleration on Blackwell SM120 GPUs; omit to disable.")

class MinimaxH3TextToVideoModelActionConfig(CommonTextToVideoModelActionConfig):
    params: MinimaxH3TextToVideoParamsConfig = Field(default_factory=MinimaxH3TextToVideoParamsConfig, description="MiniMax-H3 text-to-video generation parameters.")
