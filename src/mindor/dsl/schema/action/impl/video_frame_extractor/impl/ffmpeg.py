from typing import Union
from pydantic import Field, model_validator
from .common import CommonVideoFrameExtractorActionConfig

class FFmpegVideoFrameExtractorActionConfig(CommonVideoFrameExtractorActionConfig):
    keyframe_only: Union[bool, str] = Field(default=False, description="Whether to extract only I-frames (keyframes).")
    frame_interval: Union[int, str] = Field(default=1, description="Sampling stride applied to frames, or to keyframes when `keyframe_only` is true.")

    @model_validator(mode="after")
    def validate_frame_rate_and_keyframe_only(self):
        # `frame_rate` resamples on a uniform grid, ignoring the source's keyframe layout;
        # combining the two would silently drop the keyframe filter. Only compare
        # when `keyframe_only` is a concrete bool — a template string is deferred
        # to the driver's post-render validation.
        if self.frame_rate is not None and isinstance(self.keyframe_only, bool) and self.keyframe_only:
            raise ValueError("'frame_rate' and 'keyframe_only' are mutually exclusive; set one or the other")
        return self
