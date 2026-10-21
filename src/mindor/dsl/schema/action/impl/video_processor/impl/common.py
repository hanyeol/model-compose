from __future__ import annotations

from typing import Union, Literal, Optional, List, Tuple
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.common.color import Color
from ...common import CommonActionConfig
from ...media import VideoAudioEncodingConfig

class VideoProcessorActionMethod(str, Enum):
    RESIZE            = "resize"
    CROP              = "crop"
    PAD               = "pad"
    FLIP              = "flip"
    ROTATE            = "rotate"
    SPEED             = "speed"
    FADE_IN           = "fade-in"
    FADE_OUT          = "fade-out"
    FREEZE            = "freeze"
    REVERSE           = "reverse"
    RESAMPLE          = "resample"
    ZOOM              = "zoom"
    ADJUST_COLOR      = "adjust-color"
    ADJUST_BRIGHTNESS = "adjust-brightness"
    ADJUST_CONTRAST   = "adjust-contrast"
    ADJUST_SATURATION = "adjust-saturation"
    ADJUST_GAMMA      = "adjust-gamma"
    ADJUST_HUE        = "adjust-hue"

class VideoFreezePosition(str, Enum):
    START = "start"
    END   = "end"

class VideoScaleMode(str, Enum):
    FIT     = "fit"
    FILL    = "fill"
    STRETCH = "stretch"

class VideoFlipDirection(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"

class VideoZoomEasing(str, Enum):
    LINEAR          = "linear"
    CONSTANT_PIXELS = "constant-pixels"
    EASE_IN         = "ease-in"
    EASE_OUT        = "ease-out"

class VideoRegionConfig(BaseModel):
    x: Optional[Union[int, str]] = Field(default=None, description="X coordinate of the region's top-left corner, in input pixels.")
    y: Optional[Union[int, str]] = Field(default=None, description="Y coordinate of the region's top-left corner, in input pixels.")
    width: Optional[Union[int, str]] = Field(default=None, description="Region width in input pixels.")
    height: Optional[Union[int, str]] = Field(default=None, description="Region height in input pixels.")

    def is_empty(self) -> bool:
        return self.x is None and self.y is None and self.width is None and self.height is None

    def is_complete(self) -> bool:
        return self.x is not None and self.y is not None and self.width is not None and self.height is not None

class CommonVideoProcessorActionConfig(CommonActionConfig):
    method: VideoProcessorActionMethod = Field(..., description="Video processing operation this action performs.")
    video: Union[str, List[str]] = Field(..., description="Input video or list of videos.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the output; when unset, streams are copied without re-encoding.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos processed per batch.")

class VideoProcessorResizeActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.RESIZE]
    width: Optional[Union[int, str]] = Field(default=None, description="Target output width in pixels.")
    height: Optional[Union[int, str]] = Field(default=None, description="Target output height in pixels.")
    scale_mode: Union[VideoScaleMode, str] = Field(default=VideoScaleMode.FIT, description="How the video is fit into the target dimensions.")

class VideoProcessorCropActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.CROP]
    x: Union[int, str] = Field(..., description="X coordinate of the crop's top-left corner, in pixels.")
    y: Union[int, str] = Field(..., description="Y coordinate of the crop's top-left corner, in pixels.")
    width: Union[int, str] = Field(..., description="Crop width in pixels.")
    height: Union[int, str] = Field(..., description="Crop height in pixels.")

class VideoProcessorPadActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.PAD]
    left: Union[int, str] = Field(default=0, description="Left padding in pixels.")
    right: Union[int, str] = Field(default=0, description="Right padding in pixels.")
    top: Union[int, str] = Field(default=0, description="Top padding in pixels.")
    bottom: Union[int, str] = Field(default=0, description="Bottom padding in pixels.")
    color: Union[Color, str] = Field(default="#00000000", description="Padding color as a hex string or RGBA tuple.")

class VideoProcessorFlipActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.FLIP]
    direction: Union[VideoFlipDirection, str] = Field(..., description="Axis along which each frame is flipped.")

class VideoProcessorRotateActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ROTATE]
    angle: Union[float, str] = Field(..., description="Rotation angle in degrees, counter-clockwise.")
    expand: Union[bool, str] = Field(default=True, description="Whether the canvas expands to fit the rotated frame.")

class VideoProcessorSpeedActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.SPEED]
    speed: Union[float, str] = Field(..., description="Playback speed multiplier (e.g., 2.0 for double speed, 0.5 for half).")

class VideoProcessorFadeInActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.FADE_IN]
    start_time: Union[float, str] = Field(default=0.0, description="Time in seconds where the fade-in begins.")
    duration: Union[float, str] = Field(..., description="Fade-in length in seconds.")
    color: Union[Color, str] = Field(default="#000000", description="Color the video reveals from.")

class VideoProcessorFadeOutActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.FADE_OUT]
    start_time: Union[float, str] = Field(..., description="Time in seconds where the fade-out begins.")
    duration: Union[float, str] = Field(..., description="Fade-out length in seconds.")
    color: Union[Color, str] = Field(default="#000000", description="Color the video fades to.")

class VideoProcessorFreezeActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.FREEZE]
    position: Union[VideoFreezePosition, str] = Field(..., description="Which end to hold: `start` clones the first frame; `end` clones the last.")
    duration: Union[float, str] = Field(..., description="Freeze length in seconds.")

class VideoProcessorReverseActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.REVERSE]

class VideoProcessorResampleActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.RESAMPLE]
    frame_rate: Union[float, int, str] = Field(..., description="Target output frame rate. Frames are resampled onto a uniform grid.")

class VideoProcessorZoomActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ZOOM]
    width: Optional[Union[int, str]] = Field(default=None, description="Target output width in pixels; defaults to the input width.")
    height: Optional[Union[int, str]] = Field(default=None, description="Target output height in pixels; defaults to the input height.")
    from_: VideoRegionConfig = Field(default_factory=VideoRegionConfig, alias="from", description="Region that fills the frame at the start of the animation; defaults to the full input frame.")
    to: VideoRegionConfig = Field(default_factory=VideoRegionConfig, description="Region that fills the frame at the end of the animation; defaults to the full input frame.")
    duration: Union[float, str] = Field(..., description="Animation length in seconds.")
    easing: Union[VideoZoomEasing, str] = Field(default=VideoZoomEasing.LINEAR, description="How the zoom rate is distributed across the duration.")

    @model_validator(mode="after")
    def validate_regions(self):
        for name, region in (("from", self.from_), ("to", self.to)):
            if not region.is_empty() and not region.is_complete():
                raise ValueError(f"'{name}' region must specify all of 'x', 'y', 'width', 'height' (or none to default to the full input frame)")
        if self.from_.is_empty() and self.to.is_empty():
            raise ValueError("'zoom' requires at least one of 'from' or 'to' to be specified")
        return self

class VideoProcessorAdjustColorActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ADJUST_COLOR]
    brightness: Optional[Union[float, str]] = Field(default=None, description="Brightness multiplier; 1.0 leaves the video unchanged.")
    contrast:   Optional[Union[float, str]] = Field(default=None, description="Contrast multiplier; 1.0 leaves the video unchanged.")
    saturation: Optional[Union[float, str]] = Field(default=None, description="Saturation multiplier; 1.0 leaves the video unchanged.")
    gamma:      Optional[Union[float, str]] = Field(default=None, description="Gamma value; 1.0 leaves the video unchanged, <1.0 brightens, >1.0 darkens.")
    hue:        Optional[Union[float, str]] = Field(default=None, description="Hue rotation in degrees; 0 leaves the video unchanged.")

    @model_validator(mode="after")
    def validate_at_least_one(self):
        if all(getattr(self, field) is None for field in ("brightness", "contrast", "saturation", "gamma", "hue")):
            raise ValueError("'adjust-color' requires at least one of brightness, contrast, saturation, gamma, hue")
        return self

class VideoProcessorAdjustBrightnessActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ADJUST_BRIGHTNESS]
    factor: Union[float, str] = Field(..., description="Brightness multiplier; 1.0 leaves the video unchanged.")

class VideoProcessorAdjustContrastActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ADJUST_CONTRAST]
    factor: Union[float, str] = Field(..., description="Contrast multiplier; 1.0 leaves the video unchanged.")

class VideoProcessorAdjustSaturationActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ADJUST_SATURATION]
    factor: Union[float, str] = Field(..., description="Saturation multiplier; 1.0 leaves the video unchanged.")

class VideoProcessorAdjustGammaActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ADJUST_GAMMA]
    gamma: Union[float, str] = Field(..., description="Gamma value; 1.0 leaves the video unchanged, <1.0 brightens, >1.0 darkens.")

class VideoProcessorAdjustHueActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ADJUST_HUE]
    hue: Union[float, str] = Field(..., description="Hue rotation in degrees; 0 leaves the video unchanged.")
