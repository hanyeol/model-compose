from __future__ import annotations

from typing import Union, Literal, Optional, List
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonActionConfig
from ...media import VideoAudioEncodingConfig

class VideoMixerActionMethod(str, Enum):
    OVERLAY = "overlay"
    CONCAT  = "concat"

class VideoOverlayAnchor(str, Enum):
    TOP_LEFT      = "top-left"
    TOP_CENTER    = "top-center"
    TOP_RIGHT     = "top-right"
    CENTER_LEFT   = "center-left"
    CENTER        = "center"
    CENTER_RIGHT  = "center-right"
    BOTTOM_LEFT   = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT  = "bottom-right"

class VideoOverlayEofAction(str, Enum):
    REPEAT = "repeat"
    ENDALL = "endall"
    PASS   = "pass"

class VideoOverlayAudioMode(str, Enum):
    BASE    = "base"
    OVERLAY = "overlay"
    MIX     = "mix"
    NONE    = "none"

class VideoOverlayDurationMode(str, Enum):
    BASE     = "base"
    LONGEST  = "longest"
    SHORTEST = "shortest"

class VideoConcatTransition(str, Enum):
    FADE       = "fade"
    FADE_BLACK = "fade-black"
    FADE_WHITE = "fade-white"
    DISSOLVE   = "dissolve"
    WIPE_LEFT  = "wipe-left"
    WIPE_RIGHT = "wipe-right"
    SLIDE_UP   = "slide-up"
    SLIDE_DOWN = "slide-down"

class VideoOverlayPlacement(BaseModel):
    x: Union[int, str] = Field(default=0, description="X coordinate on the base video where the overlay is placed, in pixels.")
    y: Union[int, str] = Field(default=0, description="Y coordinate on the base video where the overlay is placed, in pixels.")
    width: Optional[Union[int, str]] = Field(default=None, description="Width the overlay is resized to before compositing, in pixels.")
    height: Optional[Union[int, str]] = Field(default=None, description="Height the overlay is resized to before compositing, in pixels.")
    anchor: Union[VideoOverlayAnchor, str] = Field(default=VideoOverlayAnchor.TOP_LEFT, description="Point of the overlay aligned at `(x, y)`.")
    opacity: Union[float, str] = Field(default=1.0, description="Alpha multiplier for the overlay, from 0.0 (transparent) to 1.0 (opaque).")
    gain: Union[float, str] = Field(default=1.0, description="Volume multiplier for the overlay's audio when mixed with other tracks.")
    start_time: Optional[Union[str, float]] = Field(default=None, description="Time the overlay first appears, as a duration string (e.g., \"2s\") or seconds.")
    end_time: Optional[Union[str, float]] = Field(default=None, description="Time the overlay disappears, as a duration string (e.g., \"5s\") or seconds.")
    eof_action: Union[VideoOverlayEofAction, str] = Field(default=VideoOverlayEofAction.REPEAT, description="Behavior after the overlay's own stream ends: `repeat` holds the last frame, `pass` shows the base only, `endall` ends the output.")

class CommonVideoMixerActionConfig(CommonActionConfig):
    method: VideoMixerActionMethod = Field(..., description="Mixing operation this action performs.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the mixed output.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sets processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether the mixed output is emitted as a byte stream instead of a temporary file.")

class VideoMixerOverlayActionConfig(CommonVideoMixerActionConfig):
    method: Literal[VideoMixerActionMethod.OVERLAY]
    video: Union[List[str], str] = Field(..., description="Base video the overlays are composited on. A list runs one output per base.")
    overlay: Union[List[str], str] = Field(..., description="Overlay videos composited on top of the base, stacked in list order.")
    placement: Union[VideoOverlayPlacement, List[VideoOverlayPlacement], List[str], str] = Field(default_factory=VideoOverlayPlacement, description="Placement per overlay. A single object broadcasts to every overlay; a list matches overlays by position.")
    audio_mode: Union[VideoOverlayAudioMode, str] = Field(default=VideoOverlayAudioMode.BASE, description="Audio track policy for the mixed output.")
    duration_mode: Union[VideoOverlayDurationMode, str] = Field(default=VideoOverlayDurationMode.BASE, description="Output duration policy relative to the base and overlays.")

class VideoMixerConcatActionConfig(CommonVideoMixerActionConfig):
    method: Literal[VideoMixerActionMethod.CONCAT]
    videos: Union[List[str], str] = Field(..., description="Videos to concatenate, in the order they appear in the output.")
    crossfade: Optional[Union[str, float]] = Field(default=None, description="Crossfade duration between adjacent videos, as a duration string (e.g., \"500ms\") or seconds.")
    transition: Union[VideoConcatTransition, str] = Field(default=VideoConcatTransition.FADE, description="Transition style applied when `crossfade` is set.")

    @model_validator(mode="after")
    def validate_videos(self) -> VideoMixerConcatActionConfig:
        if isinstance(self.videos, list) and len(self.videos) < 2:
            raise ValueError("'videos' must contain at least two entries for concat.")
        return self
