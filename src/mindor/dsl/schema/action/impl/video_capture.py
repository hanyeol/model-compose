from typing import Union, Literal, Optional
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class VideoCaptureActionMethod(str, Enum):
    CAPTURE = "capture"

class VideoCaptureSource(str, Enum):
    CAMERA = "camera"

class VideoCaptureResolution(BaseModel):
    width: Union[int, str] = Field(..., description="Frame width in pixels.")
    height: Union[int, str] = Field(..., description="Frame height in pixels.")

class VideoCaptureActionConfig(CommonActionConfig):
    method: Literal[VideoCaptureActionMethod.CAPTURE] = Field(default=VideoCaptureActionMethod.CAPTURE, description="Video capture operation this action performs.")
    source: Union[VideoCaptureSource, str] = Field(default=VideoCaptureSource.CAMERA, description="Video input source (physical or virtual camera device).")
    device: Optional[Union[int, str]] = Field(default=None, description="Camera device index or name; when unset the platform default is used.")
    resolution: Optional[VideoCaptureResolution] = Field(default=None, description="Requested frame resolution; when unset the device default is used.")
    framerate: Union[int, float, str] = Field(default=30, description="Capture frame rate in frames per second.")
    pixel_format: Optional[Union[str]] = Field(default=None, description="Requested input pixel format passed to the capture backend (e.g. 'uyvy422', 'yuyv422').")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the captured video.")
    duration: Optional[Union[str, int, float]] = Field(default=None, description="Total capture duration; when unset, capture runs until stopped.")
