from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonActionConfig

class ImageProcessorActionMethod(str, Enum):
    RESIZE            = "resize"
    CROP              = "crop"
    ROTATE            = "rotate"
    FLIP              = "flip"
    GRAYSCALE         = "grayscale"
    BLUR              = "blur"
    SHARPEN           = "sharpen"
    ADJUST_BRIGHTNESS = "adjust-brightness"
    ADJUST_CONTRAST   = "adjust-contrast"
    ADJUST_SATURATION = "adjust-saturation"
    CONCAT            = "concat"
    MERGE             = "merge"
    OVERLAY           = "overlay"
    MOSAIC            = "mosaic"

class ImageScaleMode(str, Enum):
    FIT     = "fit"
    FILL    = "fill"
    STRETCH = "stretch"

class FlipDirection(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"

class ImageConcatMode(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"
    GRID       = "grid"

class ImagePositionAnchor(str, Enum):
    TOP_LEFT      = "top-left"
    TOP_CENTER    = "top-center"
    TOP_RIGHT     = "top-right"
    CENTER_LEFT   = "center-left"
    CENTER        = "center"
    CENTER_RIGHT  = "center-right"
    BOTTOM_LEFT   = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT  = "bottom-right"

class MosaicMode(str, Enum):
    PIXELATE = "pixelate"
    BLUR     = "blur"

class CommonImageProcessorActionConfig(CommonActionConfig):
    method: ImageProcessorActionMethod = Field(..., description="Image processing operation this action performs.")
    image: Union[str, List[str]] = Field(..., description="Input image or list of images.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input images processed per batch.")

class ImageProcessorResizeActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.RESIZE]
    width: Optional[Union[int, str]] = Field(None, description="Target output width in pixels.")
    height: Optional[Union[int, str]] = Field(None, description="Target output height in pixels.")
    scale_mode: Union[ImageScaleMode, str] = Field(ImageScaleMode.FIT, description="How the image is fit into the target dimensions.")

class ImageProcessorCropActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.CROP]
    x: Union[int, str] = Field(..., description="X coordinate of the crop's top-left corner, in pixels.")
    y: Union[int, str] = Field(..., description="Y coordinate of the crop's top-left corner, in pixels.")
    width: Union[int, str] = Field(..., description="Crop width in pixels.")
    height: Union[int, str] = Field(..., description="Crop height in pixels.")

class ImageProcessorRotateActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ROTATE]
    angle: Union[float, str] = Field(..., description="Rotation angle in degrees, counter-clockwise.")
    expand: Union[bool, str] = Field(True, description="Whether the canvas expands to fit the rotated image.")

class ImageProcessorFlipActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.FLIP]
    direction: Union[FlipDirection, str] = Field(..., description="Axis along which the image is flipped.")

class ImageProcessorGrayscaleActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.GRAYSCALE]

class ImageProcessorBlurActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.BLUR]
    radius: Union[float, str] = Field(default=2.0, description="Gaussian blur radius in pixels.")

class ImageProcessorSharpenActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.SHARPEN]
    factor: Union[float, str] = Field(default=1.0, description="Sharpening strength; 1.0 leaves the image unchanged.")

class ImageProcessorAdjustBrightnessActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_BRIGHTNESS]
    factor: Union[float, str] = Field(..., description="Brightness multiplier; 1.0 leaves the image unchanged.")

class ImageProcessorAdjustContrastActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_CONTRAST]
    factor: Union[float, str] = Field(..., description="Contrast multiplier; 1.0 leaves the image unchanged.")

class ImageProcessorAdjustSaturationActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_SATURATION]
    factor: Union[float, str] = Field(..., description="Saturation multiplier; 1.0 leaves the image unchanged.")

class ImageProcessorConcatActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.CONCAT]
    mode: Union[ImageConcatMode, str] = Field(ImageConcatMode.HORIZONTAL, description="Layout used to arrange the images.")
    columns: Optional[Union[int, str]] = Field(default=None, description="Number of columns when `mode` is `grid`.")
    rows: Optional[Union[int, str]] = Field(default=None, description="Number of rows when `mode` is `grid`.")
    spacing: Union[int, str] = Field(default=0, description="Spacing in pixels between adjacent images.")
    background: Union[str, Tuple[int, int, int, int], List[int]] = Field(default="#00000000", description="Canvas background color as a hex string or RGBA tuple.")

class ImageProcessorMergeActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.MERGE]
    anchor: Union[ImagePositionAnchor, str] = Field(default=ImagePositionAnchor.CENTER, description="Alignment applied to each image on the shared canvas.")
    background: Union[str, Tuple[int, int, int, int], List[int]] = Field(default="#00000000", description="Canvas background color as a hex string or RGBA tuple.")

class ImageProcessorOverlayActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.OVERLAY]
    overlay: str = Field(..., description="Overlay image.")
    x: Union[int, str] = Field(..., description="X coordinate on the base image where the overlay is placed.")
    y: Union[int, str] = Field(..., description="Y coordinate on the base image where the overlay is placed.")
    width: Optional[Union[int, str]] = Field(default=None, description="Width the overlay is resized to before pasting, in pixels.")
    height: Optional[Union[int, str]] = Field(default=None, description="Height the overlay is resized to before pasting, in pixels.")
    anchor: Union[ImagePositionAnchor, str] = Field(default=ImagePositionAnchor.TOP_LEFT, description="Point of the overlay aligned at `(x, y)`.")
    opacity: Union[float, str] = Field(default=1.0, description="Alpha multiplier for the overlay, from 0.0 to 1.0.")

class ImageProcessorMosaicActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.MOSAIC]
    mode: Union[MosaicMode, str] = Field(default=MosaicMode.PIXELATE, description="Mosaic algorithm applied to the target region.")
    x: Optional[Union[int, str]] = Field(default=None, description="X coordinate of the region's top-left corner, in pixels. Omit (with y/width/height) to apply to the whole image.")
    y: Optional[Union[int, str]] = Field(default=None, description="Y coordinate of the region's top-left corner, in pixels.")
    width: Optional[Union[int, str]] = Field(default=None, description="Region width in pixels.")
    height: Optional[Union[int, str]] = Field(default=None, description="Region height in pixels.")
    block_size: Optional[Union[int, str]] = Field(default=None, description="Pixelate block size in pixels. Mutually exclusive with `block_scale`; defaults to 16 when neither is set.")
    block_scale: Optional[Union[float, str]] = Field(default=None, description="Pixelate block size relative to the region's shorter side, from 0 to 1. Mutually exclusive with `block_size`.")
    min_block_size: Union[int, str] = Field(default=8, description="Lower bound in pixels on the computed pixelate block size when `block_scale` is used.")
    max_block_size: Union[int, str] = Field(default=32, description="Upper bound in pixels on the computed pixelate block size when `block_scale` is used.")
    blur_radius: Union[float, str] = Field(default=8.0, description="Blur radius in pixels, applied when `mode` is `blur`.")
    corner_radius: Optional[Union[int, str]] = Field(default=None, description="Rounded-corner radius in pixels. Mutually exclusive with `corner_scale`.")
    corner_scale: Optional[Union[float, str]] = Field(default=None, description="Rounded-corner radius relative to the region's shorter side, from 0 to 0.5. Mutually exclusive with `corner_radius`.")

    @model_validator(mode="after")
    def validate_block_size_or_scale(self) -> ImageProcessorMosaicActionConfig:
        if self.block_size is not None and self.block_scale is not None:
            raise ValueError("'block_size' and 'block_scale' are mutually exclusive; specify only one.")
        return self

    @model_validator(mode="after")
    def validate_corner_radius_or_scale(self) -> ImageProcessorMosaicActionConfig:
        if self.corner_radius is not None and self.corner_scale is not None:
            raise ValueError("'corner_radius' and 'corner_scale' are mutually exclusive; specify only one.")
        return self
