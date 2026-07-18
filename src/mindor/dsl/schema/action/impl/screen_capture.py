from typing import Union, Literal, Optional
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class ScreenCaptureActionMethod(str, Enum):
    CAPTURE = "capture"

class ScreenCaptureVideoSource(str, Enum):
    DISPLAY = "display"
    REGION  = "region"

class ScreenCaptureAudioSource(str, Enum):
    SYSTEM     = "system"
    MICROPHONE = "microphone"
    NONE       = "none"

class ScreenCaptureRegion(BaseModel):
    x: Union[int, str] = Field(..., description="Left edge in pixels from the top-left of the target display.")
    y: Union[int, str] = Field(..., description="Top edge in pixels from the top-left of the target display.")
    width: Union[int, str] = Field(..., description="Region width in pixels.")
    height: Union[int, str] = Field(..., description="Region height in pixels.")

class ScreenCaptureActionConfig(CommonActionConfig):
    method: Literal[ScreenCaptureActionMethod.CAPTURE] = Field(default=ScreenCaptureActionMethod.CAPTURE, description="Screen capture action method.")
    video_source: Union[ScreenCaptureVideoSource, str] = Field(default=ScreenCaptureVideoSource.DISPLAY, description="Capture target kind.")
    audio_source: Union[ScreenCaptureAudioSource, str] = Field(default=ScreenCaptureAudioSource.SYSTEM, description="Which audio to capture: 'system' loopback, 'microphone', or 'none'.")
    display: Union[int, str] = Field(default=0, description="Display index when video_source='display' or 'region'.")
    region: Optional[ScreenCaptureRegion] = Field(default=None, description="Region rectangle on the target display; required when video_source='region'.")
    include_video: Union[bool, str] = Field(default=True, description="Include a video track in the capture.")
    include_audio: Union[bool, str] = Field(default=True, description="Include an audio track in the capture.")
    framerate: Union[int, float, str] = Field(default=30, description="Capture framerate (frames per second).")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Video/audio encoding settings.")
    duration: Optional[Union[str, int, float]] = Field(default=None, description="Total capture duration. None = capture until stopped.")

    @model_validator(mode="after")
    def validate_tracks(self):
        if not self.include_video and not self.include_audio:
            raise ValueError("At least one of 'include_video' or 'include_audio' must be True.")
        return self

    @model_validator(mode="after")
    def validate_region(self):
        # Only enforce the region-required rule for the enum literal. When
        # video_source is a variable expression like "${input.video_source}",
        # pydantic keeps it as a raw string and the runtime resolver validates
        # the resolved value against the region param.
        if self.video_source == ScreenCaptureVideoSource.REGION and self.region is None:
            raise ValueError("'region' must be provided when video_source='region'.")
        return self
