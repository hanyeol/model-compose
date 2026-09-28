from typing import Union
from pydantic import Field, model_validator
from .common import CommonVideoFrameExtractorActionConfig

class FFmpegVideoFrameExtractorActionConfig(CommonVideoFrameExtractorActionConfig):
    keyframe_only: Union[bool, str] = Field(default=False, description="Whether to extract only I-frames (keyframes).")
    frame_interval: Union[int, str] = Field(default=1, description="Sampling stride applied to frames, or to keyframes when `keyframe_only` is true.")

    @model_validator(mode="after")
    def validate_fps_and_keyframe_only(self):
        # `fps` resamples on a uniform grid, ignoring the source's keyframe layout;
        # combining the two would silently drop the keyframe filter.
        if self.fps is not None and self.keyframe_only:
            raise ValueError("'fps' and 'keyframe_only' are mutually exclusive; set one or the other")
        return self
