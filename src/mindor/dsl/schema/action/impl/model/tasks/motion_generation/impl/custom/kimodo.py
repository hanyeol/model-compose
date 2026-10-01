from typing import Union, Literal, Optional, List, Annotated
from pydantic import Field
from ..common import (
    CommonMotionGenerationParamsConfig,
    CommonMotionGenerationModelActionConfig,
    MotionGenerationActionMethod,
)

class KimodoMotionGenerationParamsConfig(CommonMotionGenerationParamsConfig):
    duration: Union[float, str] = Field(default=4.0, description="Motion duration in seconds.")
    num_samples: Union[int, str] = Field(default=1, description="Number of motion variations to generate.")
    diffusion_steps: Union[int, str] = Field(default=10, description="Number of DDIM denoising steps.")
    cfg_weight: Union[float, List[float], str] = Field(default=2.0, description="Classifier-free guidance weight; a two-element list [text, constraint] when driving separated CFG.")
    post_processing: Union[bool, str] = Field(default=True, description="Whether to apply foot-skate and constraint cleanup to the generated motion.")

class CommonKimodoMotionGenerationModelActionConfig(CommonMotionGenerationModelActionConfig):
    params: KimodoMotionGenerationParamsConfig = Field(default_factory=KimodoMotionGenerationParamsConfig, description="Kimodo motion generation parameters.")

class KimodoMotionGenerationModelGenerateActionConfig(CommonKimodoMotionGenerationModelActionConfig):
    method: Literal[MotionGenerationActionMethod.GENERATE]
    prompt: Union[str, List[str]] = Field(..., description="Natural-language description of the desired motion.")

KimodoMotionGenerationModelActionConfig = Annotated[
    Union[
        KimodoMotionGenerationModelGenerateActionConfig,
    ],
    Field(discriminator="method")
]
