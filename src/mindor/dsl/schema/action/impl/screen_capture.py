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
    WINDOW  = "window"

class ScreenCaptureAudioSource(str, Enum):
    SYSTEM     = "system"
    MICROPHONE = "microphone"
    NONE       = "none"

class ScreenCaptureRegion(BaseModel):
    x: Union[int, str] = Field(..., description="Left edge in pixels from the top-left of the target display.")
    y: Union[int, str] = Field(..., description="Top edge in pixels from the top-left of the target display.")
    width: Union[int, str] = Field(..., description="Region width in pixels.")
    height: Union[int, str] = Field(..., description="Region height in pixels.")

class ScreenCaptureWindow(BaseModel):
    title: Optional[str] = Field(default=None, description="Case-insensitive substring matched against the window title.")
    app: Optional[str] = Field(default=None, description="Case-insensitive substring matched against the owning application name.")

    @model_validator(mode="after")
    def validate_selectors(self):
        if not self.title and not self.app:
            raise ValueError("At least one of 'title' or 'app' must be provided.")
        return self

class ScreenCaptureActionConfig(CommonActionConfig):
    method: Literal[ScreenCaptureActionMethod.CAPTURE] = Field(default=ScreenCaptureActionMethod.CAPTURE, description="Screen capture operation this action performs.")
    video_source: Union[ScreenCaptureVideoSource, str] = Field(default=ScreenCaptureVideoSource.DISPLAY, description="Kind of screen region captured for the video track.")
    audio_source: Union[ScreenCaptureAudioSource, str] = Field(default=ScreenCaptureAudioSource.SYSTEM, description="Audio source captured alongside the video (system loopback, microphone, or none).")
    display: Union[int, str] = Field(default=0, description="Index of the display captured when `video_source` is `display` or `region`.")
    region: Optional[ScreenCaptureRegion] = Field(default=None, description="Region rectangle on the target display. Required when `video_source` is `region`.")
    window: Optional[ScreenCaptureWindow] = Field(default=None, description="Window selector. Required when `video_source` is `window`.")
    include_video: Union[bool, str] = Field(default=True, description="Whether a video track is included in the capture.")
    include_audio: Union[bool, str] = Field(default=True, description="Whether an audio track is included in the capture.")
    framerate: Union[int, float, str] = Field(default=30, description="Capture frame rate in frames per second.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the captured video and audio.")
    duration: Optional[Union[str, int, float]] = Field(default=None, description="Total capture duration; when unset, capture runs until stopped.")

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

    @model_validator(mode="after")
    def validate_window(self):
        if self.video_source == ScreenCaptureVideoSource.WINDOW and self.window is None:
            raise ValueError("'window' must be provided when video_source='window'.")
        return self
