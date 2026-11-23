from __future__ import annotations

from typing import Union, Literal, Optional, List, Annotated
from pydantic import BaseModel, Field, model_validator
from ..common import (
    ImageGenerationActionMethod,
    CommonImageGenerationModelGenerateActionConfig,
    CommonImageGenerationModelEditActionConfig,
    CommonImageGenerationParamsConfig,
)

class MinimaxH3ImageGenerationSolAttnConfig(BaseModel):
    tau: Union[float, str] = Field(default=1.0, description="Sol-Attn routing threshold scale (τ); higher skips more KV blocks.")
    thresh_type: Union[Literal["diag", "exact"], str] = Field(default="diag", description="Threshold estimation mode.")
    dense_steps: Optional[Union[int, str]] = Field(default=None, description="Run the last N denoising steps fully dense.")
    step_off: Optional[Union[float, str]] = Field(default=None, description="Dense fraction at the tail of the schedule.")

class MinimaxH3ImageGenerationParamsConfig(CommonImageGenerationParamsConfig):
    min_generation_area: Union[int, str] = Field(default=4194304, description="Smallest area in pixels used for the internal generation canvas; smaller requests upscale to this and resize back after decoding.")
    sol_attn: Optional[MinimaxH3ImageGenerationSolAttnConfig] = Field(default=None, description="Sol-Attn sparse attention acceleration on Blackwell SM120 GPUs; omit to disable.")

class MinimaxH3ImageGenerationModelGenerateActionConfig(CommonImageGenerationModelGenerateActionConfig):
    method: Literal[ImageGenerationActionMethod.GENERATE] = Field(default=ImageGenerationActionMethod.GENERATE)
    params: MinimaxH3ImageGenerationParamsConfig = Field(default_factory=MinimaxH3ImageGenerationParamsConfig, description="MiniMax-H3 image generation parameters.")

class MinimaxH3ImageGenerationModelEditActionConfig(CommonImageGenerationModelEditActionConfig):
    method: Literal[ImageGenerationActionMethod.EDIT] = Field(default=ImageGenerationActionMethod.EDIT)
    image: Union[str, List[str]] = Field(..., description="Reference image or images used as the editing target; order defines the `<Picture N>` label order used in the prompt.")
    params: MinimaxH3ImageGenerationParamsConfig = Field(default_factory=MinimaxH3ImageGenerationParamsConfig, description="MiniMax-H3 image editing parameters.")

    @model_validator(mode="after")
    def validate_reference_counts(self) -> "MinimaxH3ImageGenerationModelEditActionConfig":
        # H3-Image upstream cap: up to 16 reference images per edit.
        # Only static-list forms are checked here; variable references (`${...}`)
        # resolve later and are left to the driver to validate at runtime.
        if isinstance(self.image, list) and len(self.image) > 16:
            raise ValueError("MiniMax-H3 image editing accepts at most 16 reference images.")
        return self

MinimaxH3ImageGenerationModelActionConfig = Annotated[
    Union[
        MinimaxH3ImageGenerationModelGenerateActionConfig,
        MinimaxH3ImageGenerationModelEditActionConfig,
    ],
    Field(discriminator="method")
]
