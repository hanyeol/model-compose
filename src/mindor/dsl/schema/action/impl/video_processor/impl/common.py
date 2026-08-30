from __future__ import annotations

from typing import Union, Literal, Optional, List, Tuple
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig
from ...media import VideoAudioEncodingConfig

class VideoProcessorActionMethod(str, Enum):
    RESIZE = "resize"
    CROP   = "crop"
    PAD    = "pad"
    FLIP   = "flip"
    ROTATE = "rotate"

class VideoScaleMode(str, Enum):
    FIT     = "fit"
    FILL    = "fill"
    STRETCH = "stretch"

class VideoFlipDirection(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"

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
    color: Union[str, Tuple[int, int, int, int], List[int]] = Field(default="#00000000", description="Padding color as a hex string or RGBA tuple.")

class VideoProcessorFlipActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.FLIP]
    direction: Union[VideoFlipDirection, str] = Field(..., description="Axis along which each frame is flipped.")

class VideoProcessorRotateActionConfig(CommonVideoProcessorActionConfig):
    method: Literal[VideoProcessorActionMethod.ROTATE]
    angle: Union[float, str] = Field(..., description="Rotation angle in degrees, counter-clockwise.")
    expand: Union[bool, str] = Field(default=True, description="Whether the canvas expands to fit the rotated frame.")
