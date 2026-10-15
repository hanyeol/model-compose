from __future__ import annotations

from typing import Union, Literal, Optional, Annotated
from enum import Enum
from pydantic import Field, model_validator
from mindor.dsl.schema.common.color import Color
from .common import (
    CommonImageProcessorActionConfig,
    ImageProcessorActionMethod,
    ImageScaleMode,
    FlipDirection,
    ImageConcatMode,
    ImagePositionAnchor,
)

class NativeImageProcessorActionMethod(ImageProcessorActionMethod):
    RESIZE            = "resize"
    CROP              = "crop"
    ROTATE            = "rotate"
    FLIP              = "flip"
    GRAYSCALE         = "grayscale"
    BLUR              = "blur"
    SHARPEN           = "sharpen"
    ADJUST_COLOR      = "adjust-color"
    ADJUST_BRIGHTNESS = "adjust-brightness"
    ADJUST_CONTRAST   = "adjust-contrast"
    ADJUST_SATURATION = "adjust-saturation"
    ADJUST_GAMMA      = "adjust-gamma"
    ADJUST_HUE        = "adjust-hue"
    CONCAT            = "concat"
    MERGE             = "merge"
    OVERLAY           = "overlay"
    MOSAIC            = "mosaic"

class MosaicMode(str, Enum):
    PIXELATE = "pixelate"
    BLUR     = "blur"

class NativeImageProcessorResizeActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.RESIZE]
    width: Optional[Union[int, str]] = Field(None, description="Target output width in pixels.")
    height: Optional[Union[int, str]] = Field(None, description="Target output height in pixels.")
    scale_mode: Union[ImageScaleMode, str] = Field(ImageScaleMode.FIT, description="How the image is fit into the target dimensions.")

class NativeImageProcessorCropActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.CROP]
    x: Union[int, str] = Field(..., description="X coordinate of the crop's top-left corner, in pixels.")
    y: Union[int, str] = Field(..., description="Y coordinate of the crop's top-left corner, in pixels.")
    width: Union[int, str] = Field(..., description="Crop width in pixels.")
    height: Union[int, str] = Field(..., description="Crop height in pixels.")

class NativeImageProcessorRotateActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.ROTATE]
    angle: Union[float, str] = Field(..., description="Rotation angle in degrees, counter-clockwise.")
    expand: Union[bool, str] = Field(True, description="Whether the canvas expands to fit the rotated image.")

class NativeImageProcessorFlipActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.FLIP]
    direction: Union[FlipDirection, str] = Field(..., description="Axis along which the image is flipped.")

class NativeImageProcessorGrayscaleActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.GRAYSCALE]

class NativeImageProcessorBlurActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.BLUR]
    radius: Union[float, str] = Field(default=2.0, description="Gaussian blur radius in pixels.")

class NativeImageProcessorSharpenActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.SHARPEN]
    factor: Union[float, str] = Field(default=1.0, description="Sharpening strength; 1.0 leaves the image unchanged.")

class NativeImageProcessorAdjustColorActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.ADJUST_COLOR]
    brightness: Optional[Union[float, str]] = Field(default=None, description="Brightness multiplier; 1.0 leaves the image unchanged.")
    contrast:   Optional[Union[float, str]] = Field(default=None, description="Contrast multiplier; 1.0 leaves the image unchanged.")
    saturation: Optional[Union[float, str]] = Field(default=None, description="Saturation multiplier; 1.0 leaves the image unchanged.")
    gamma:      Optional[Union[float, str]] = Field(default=None, description="Gamma value; 1.0 leaves the image unchanged, <1.0 brightens, >1.0 darkens.")
    hue:        Optional[Union[float, str]] = Field(default=None, description="Hue rotation in degrees; 0 leaves the image unchanged.")

    @model_validator(mode="after")
    def validate_at_least_one(self):
        if all(getattr(self, field) is None for field in ("brightness", "contrast", "saturation", "gamma", "hue")):
            raise ValueError("'adjust-color' requires at least one of brightness, contrast, saturation, gamma, hue")
        return self

class NativeImageProcessorAdjustBrightnessActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.ADJUST_BRIGHTNESS]
    factor: Union[float, str] = Field(..., description="Brightness multiplier; 1.0 leaves the image unchanged.")

class NativeImageProcessorAdjustContrastActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.ADJUST_CONTRAST]
    factor: Union[float, str] = Field(..., description="Contrast multiplier; 1.0 leaves the image unchanged.")

class NativeImageProcessorAdjustSaturationActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.ADJUST_SATURATION]
    factor: Union[float, str] = Field(..., description="Saturation multiplier; 1.0 leaves the image unchanged.")

class NativeImageProcessorAdjustGammaActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.ADJUST_GAMMA]
    gamma: Union[float, str] = Field(..., description="Gamma value; 1.0 leaves the image unchanged, <1.0 brightens, >1.0 darkens.")

class NativeImageProcessorAdjustHueActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.ADJUST_HUE]
    hue: Union[float, str] = Field(..., description="Hue rotation in degrees; 0 leaves the image unchanged.")

class NativeImageProcessorConcatActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.CONCAT]
    mode: Union[ImageConcatMode, str] = Field(ImageConcatMode.HORIZONTAL, description="Layout used to arrange the images.")
    columns: Optional[Union[int, str]] = Field(default=None, description="Number of columns when `mode` is `grid`.")
    rows: Optional[Union[int, str]] = Field(default=None, description="Number of rows when `mode` is `grid`.")
    spacing: Union[int, str] = Field(default=0, description="Spacing in pixels between adjacent images.")
    background: Union[Color, str] = Field(default="#00000000", description="Canvas background color as a hex string or RGBA tuple.")

class NativeImageProcessorMergeActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.MERGE]
    anchor: Union[ImagePositionAnchor, str] = Field(default=ImagePositionAnchor.CENTER, description="Alignment applied to each image on the shared canvas.")
    background: Union[Color, str] = Field(default="#00000000", description="Canvas background color as a hex string or RGBA tuple.")

class NativeImageProcessorOverlayActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.OVERLAY]
    overlay: str = Field(..., description="Overlay image.")
    x: Union[int, str] = Field(..., description="X coordinate on the base image where the overlay is placed.")
    y: Union[int, str] = Field(..., description="Y coordinate on the base image where the overlay is placed.")
    width: Optional[Union[int, str]] = Field(default=None, description="Width the overlay is resized to before pasting, in pixels.")
    height: Optional[Union[int, str]] = Field(default=None, description="Height the overlay is resized to before pasting, in pixels.")
    anchor: Union[ImagePositionAnchor, str] = Field(default=ImagePositionAnchor.TOP_LEFT, description="Point of the overlay aligned at `(x, y)`.")
    opacity: Union[float, str] = Field(default=1.0, description="Alpha multiplier for the overlay, from 0.0 to 1.0.")
    feather_radius: Optional[Union[int, str]] = Field(default=None, description="Gaussian feather radius in pixels for softening the overlay edges. Mutually exclusive with `feather_scale`.")
    feather_scale: Optional[Union[float, str]] = Field(default=None, description="Feather radius relative to the overlay's shorter side, from 0 to 0.5. Mutually exclusive with `feather_radius`.")

    @model_validator(mode="after")
    def validate_feather_radius_or_scale(self) -> NativeImageProcessorOverlayActionConfig:
        if self.feather_radius is not None and self.feather_scale is not None:
            raise ValueError("'feather_radius' and 'feather_scale' are mutually exclusive; specify only one.")
        return self

class NativeImageProcessorMosaicActionConfig(CommonImageProcessorActionConfig):
    method: Literal[NativeImageProcessorActionMethod.MOSAIC]
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
    def validate_block_size_or_scale(self) -> NativeImageProcessorMosaicActionConfig:
        if self.block_size is not None and self.block_scale is not None:
            raise ValueError("'block_size' and 'block_scale' are mutually exclusive; specify only one.")
        return self

    @model_validator(mode="after")
    def validate_corner_radius_or_scale(self) -> NativeImageProcessorMosaicActionConfig:
        if self.corner_radius is not None and self.corner_scale is not None:
            raise ValueError("'corner_radius' and 'corner_scale' are mutually exclusive; specify only one.")
        return self

NativeImageProcessorActionConfig = Annotated[
    Union[
        NativeImageProcessorResizeActionConfig,
        NativeImageProcessorCropActionConfig,
        NativeImageProcessorRotateActionConfig,
        NativeImageProcessorFlipActionConfig,
        NativeImageProcessorGrayscaleActionConfig,
        NativeImageProcessorBlurActionConfig,
        NativeImageProcessorSharpenActionConfig,
        NativeImageProcessorAdjustColorActionConfig,
        NativeImageProcessorAdjustBrightnessActionConfig,
        NativeImageProcessorAdjustContrastActionConfig,
        NativeImageProcessorAdjustSaturationActionConfig,
        NativeImageProcessorAdjustGammaActionConfig,
        NativeImageProcessorAdjustHueActionConfig,
        NativeImageProcessorConcatActionConfig,
        NativeImageProcessorMergeActionConfig,
        NativeImageProcessorOverlayActionConfig,
        NativeImageProcessorMosaicActionConfig,
    ],
    Field(discriminator="method")
]
