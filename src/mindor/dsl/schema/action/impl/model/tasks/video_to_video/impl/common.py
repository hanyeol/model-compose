from __future__ import annotations

from typing import Union, Optional, List, Any
from pydantic import BaseModel, Field, model_validator
from ...common import CommonModelActionConfig

class CommonVideoToVideoParamsConfig(BaseModel):
    num_frames: Optional[Union[int, str]] = Field(default=None, description="Number of frames to sample from the input video; defaults to using all input frames.")
    fps: Union[int, str] = Field(default=8, description="Output video frame rate.")
    height: Optional[Union[int, str]] = Field(default=None, description="Output video height; defaults to the input video height when unset.")
    width: Optional[Union[int, str]] = Field(default=None, description="Output video width; defaults to the input video width when unset.")

class CommonVideoToVideoModelActionConfig(CommonModelActionConfig):
    video: Optional[Union[str, List[str]]] = Field(default=None, description="Input video (path or URL) used as the motion source.")
    frames: Optional[Union[Any, List[Any], List[List[Any]], str]] = Field(default=None, description="Input frames used as the motion source; a single video's frames, a list of frames, a list of per-video frame batches, or a stream of batches.")
    prompt: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Text prompt guiding the restyled output.")
    negative_prompt: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Text describing content to avoid in the generated video.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonVideoToVideoParamsConfig = Field(default_factory=CommonVideoToVideoParamsConfig, description="Frame count, resolution, and sampling parameters applied to generation.")

    @model_validator(mode="after")
    def validate_video_or_frames(self) -> CommonVideoToVideoModelActionConfig:
        if (self.video is None) == (self.frames is None):
            raise ValueError("Exactly one of `video` or `frames` must be provided.")
        return self
