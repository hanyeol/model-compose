from typing import Union, Optional, List
from pydantic import Field, model_validator
from ...common import CommonActionConfig

class CommonVideoFrameExtractorActionConfig(CommonActionConfig):
    video: Union[str, List[str]] = Field(..., description="Video source or list of sources to extract frames from.")
    frame_interval: Union[int, str] = Field(default=1, description="Sampling stride applied to frames.")
    frame_rate: Optional[Union[int, float, str]] = Field(default=None, description="Output sampling frame rate.")
    start_time: Optional[str] = Field(default=None, description="Time in the source at which extraction begins (e.g., 00:01:00, 60s).")
    end_time: Optional[str] = Field(default=None, description="Time in the source at which extraction stops (e.g., 00:05:00, 300s).")
    max_frame_count: Optional[Union[int, str]] = Field(default=None, description="Maximum number of frames to extract.")
    filename_format: Optional[str] = Field(default=None, description="Per-frame filename pattern (e.g., frame-%04d.png).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether frames are emitted incrementally as they are produced.")

    @model_validator(mode="after")
    def validate_frame_rate(self):
        if self.frame_rate is not None:
            if isinstance(self.frame_rate, (int, float)) and self.frame_rate <= 0:
                raise ValueError(f"'frame_rate' must be > 0, got {self.frame_rate}")
            # `frame_rate` resamples to a uniform grid; combining it with an
            # index-based stride wastes work at best and creates an
            # ambiguous ordering (resample first or stride first?) at worst.
            # Only compare when both sides are concrete — a template string
            # like "${input.stride}" never equals 1 as a Python value even
            # when it resolves to 1 at render time, so the check is deferred
            # to the driver's post-render validation.
            if isinstance(self.frame_interval, int) and self.frame_interval != 1:
                raise ValueError("'frame_rate' and 'frame_interval' are mutually exclusive; set one or the other")
        return self
