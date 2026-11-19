from __future__ import annotations

from typing import Union, Literal, Optional, List, Any
from pydantic import BaseModel, Field, model_validator
from ..common import CommonVideoToVideoParamsConfig, CommonVideoToVideoModelActionConfig

class MinimaxH3VideoToVideoSolAttnConfig(BaseModel):
    tau: Union[float, str] = Field(default=1.0, description="Sol-Attn routing threshold scale (τ); higher skips more KV blocks.")
    thresh_type: Union[Literal["diag", "exact"], str] = Field(default="diag", description="Threshold estimation mode.")
    dense_steps: Optional[Union[int, str]] = Field(default=None, description="Run the last N denoising steps fully dense.")
    step_off: Optional[Union[float, str]] = Field(default=None, description="Dense fraction at the tail of the schedule.")

class MinimaxH3VideoToVideoParamsConfig(CommonVideoToVideoParamsConfig):
    num_frames: Union[int, str] = Field(default=124, description="Number of frames to generate; snapped up to 17*n+5 and clamped to the 124..345 range (5..15 s at 24 fps).")
    inference_steps: Union[int, str] = Field(default=50, description="Number of sigma grid points (including the terminal 0), one less than the model evaluations.")
    guidance_scale: Union[float, str] = Field(default=1.0, description="Classifier-free guidance scale applied during sampling.")
    video_shift: Optional[Union[float, str]] = Field(default=None, description="Flow-matching timestep shift applied to the video scheduler.")
    audio_shift: Optional[Union[float, str]] = Field(default=None, description="Flow-matching timestep shift applied to the audio scheduler.")
    sol_attn: Optional[MinimaxH3VideoToVideoSolAttnConfig] = Field(default=None, description="Sol-Attn sparse attention acceleration on Blackwell SM120 GPUs; omit to disable.")

class MinimaxH3VideoToVideoModelActionConfig(CommonVideoToVideoModelActionConfig):
    negative_prompt: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Text describing content to avoid in the generated video.")
    reference_image: Optional[Union[Any, List[Any]]] = Field(default=None, description="Reference image(s) passed to the ref2va workflow; the order you list is the `<Picture N>` label order used in the prompt.")
    reference_audio: Optional[Union[Any, List[Any]]] = Field(default=None, description="Reference audio clip(s) passed to the ref2va workflow; the order you list is the `<Audio N>` label order used in the prompt.")
    params: MinimaxH3VideoToVideoParamsConfig = Field(default_factory=MinimaxH3VideoToVideoParamsConfig, description="MiniMax-H3 video-to-video (ref2va) generation parameters.")

    @model_validator(mode="after")
    def validate_inputs(self) -> "MinimaxH3VideoToVideoModelActionConfig":
        # ref2va runs from prompt + references; the driving clip is optional, so
        # accept any combination except `video` + `frames` together, and require
        # at least one of the four input slots to be present.
        if self.video is not None and self.frames is not None:
            raise ValueError("At most one of `video` or `frames` may be set.")
        if all(value is None for value in (self.video, self.frames, self.reference_image, self.reference_audio)):
            raise ValueError("MiniMax-H3 ref2va requires at least one of `video`, `frames`, `reference_image`, or `reference_audio`.")
        return self

    @model_validator(mode="after")
    def validate_reference_counts(self) -> "MinimaxH3VideoToVideoModelActionConfig":
        # ref2va upstream caps: up to 9 images, 3 videos, 3 audio clips.
        # Only static-list forms are checked here; variable references (`${...}`)
        # resolve later and are left to the driver to validate at runtime.
        if isinstance(self.video, list) and len(self.video) > 3:
            raise ValueError("MiniMax-H3 ref2va accepts at most 3 video references.")
        if isinstance(self.reference_image, list) and len(self.reference_image) > 9:
            raise ValueError("MiniMax-H3 ref2va accepts at most 9 image references.")
        if isinstance(self.reference_audio, list) and len(self.reference_audio) > 3:
            raise ValueError("MiniMax-H3 ref2va accepts at most 3 audio references.")
        return self
