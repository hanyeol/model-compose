from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import Field
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
    COMPRESS          = "compress"

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

class ImageOverlayAnchor(str, Enum):
    TOP_LEFT = "top-left"
    CENTER   = "center"

class ImageCompressStrategy(str, Enum):
    LOSSLESS  = "lossless"
    OPTIMIZED = "optimized"
    QUANTIZED = "quantized"

class CommonImageProcessorActionConfig(CommonActionConfig):
    method: ImageProcessorActionMethod = Field(..., description="Image processor method.")
    image: Union[str, List[str]] = Field(..., description="Input image(s) (file path, base64 string, or variable reference).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input images per batch.")

class ImageProcessorResizeActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.RESIZE]
    width: Optional[Union[int, str]] = Field(None, description="Target width in pixels.")
    height: Optional[Union[int, str]] = Field(None, description="Target height in pixels.")
    scale_mode: Union[ImageScaleMode, str] = Field(ImageScaleMode.FIT, description="Resize mode.")

class ImageProcessorCropActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.CROP]
    x: Union[int, str] = Field(..., description="X coordinate of top-left corner.")
    y: Union[int, str] = Field(..., description="Y coordinate of top-left corner.")
    width: Union[int, str] = Field(..., description="Crop width in pixels.")
    height: Union[int, str] = Field(..., description="Crop height in pixels.")

class ImageProcessorRotateActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ROTATE]
    angle: Union[float, str] = Field(..., description="Rotation angle in degrees.")
    expand: Union[bool, str] = Field(True, description="Expand canvas to fit rotated image.")

class ImageProcessorFlipActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.FLIP]
    direction: Union[FlipDirection, str] = Field(..., description="Flip direction.")

class ImageProcessorGrayscaleActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.GRAYSCALE]

class ImageProcessorBlurActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.BLUR]
    radius: Union[float, str] = Field(default=2.0, description="Blur radius in pixels.")

class ImageProcessorSharpenActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.SHARPEN]
    factor: Union[float, str] = Field(default=1.0, description="Sharpening factor.")

class ImageProcessorAdjustBrightnessActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_BRIGHTNESS]
    factor: Union[float, str] = Field(..., description="Brightness factor.")

class ImageProcessorAdjustContrastActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_CONTRAST]
    factor: Union[float, str] = Field(..., description="Contrast factor.")

class ImageProcessorAdjustSaturationActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.ADJUST_SATURATION]
    factor: Union[float, str] = Field(..., description="Saturation factor.")

class ImageProcessorConcatActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.CONCAT]
    mode: Union[ImageConcatMode, str] = Field(ImageConcatMode.HORIZONTAL, description="Concat layout mode.")
    columns: Optional[Union[int, str]] = Field(default=None, description="Number of columns for grid mode.")
    rows: Optional[Union[int, str]] = Field(default=None, description="Number of rows for grid mode.")
    spacing: Union[int, str] = Field(default=0, description="Pixel spacing between images for horizontal, vertical, and grid modes.")
    background: Union[str, Tuple[int, int, int, int], List[int]] = Field(default="#00000000", description="Background color (hex or RGBA tuple).")

class ImageProcessorMergeActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.MERGE]
    background: Union[str, Tuple[int, int, int, int], List[int]] = Field(default="#00000000", description="Background color (hex or RGBA tuple).")

class ImageProcessorOverlayActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.OVERLAY]
    overlay: str = Field(..., description="Overlay image (file path, base64 string, or variable reference).")
    x: Union[int, str] = Field(..., description="X coordinate to place the overlay on the base image.")
    y: Union[int, str] = Field(..., description="Y coordinate to place the overlay on the base image.")
    width: Optional[Union[int, str]] = Field(default=None, description="Resize overlay width in pixels before pasting.")
    height: Optional[Union[int, str]] = Field(default=None, description="Resize overlay height in pixels before pasting.")
    anchor: Union[ImageOverlayAnchor, str] = Field(default=ImageOverlayAnchor.TOP_LEFT, description="Anchor point for (x, y): 'top-left' or 'center'.")
    opacity: Union[float, str] = Field(default=1.0, description="Alpha multiplier for the overlay (0.0-1.0).")

class ImageProcessorCompressActionConfig(CommonImageProcessorActionConfig):
    method: Literal[ImageProcessorActionMethod.COMPRESS]
    strategy: Union[ImageCompressStrategy, str] = Field(default=ImageCompressStrategy.LOSSLESS, description="PNG compression strategy.")
    compress_level: Union[int, str] = Field(default=9, description="DEFLATE compression level (0-9). Higher is smaller and slower.")
    min_quality: Optional[Union[int, str]] = Field(default=None, description="Quantized minimum quality (0-100). Save fails if output would fall below this.")
    max_quality: Optional[Union[int, str]] = Field(default=None, description="Quantized maximum quality (0-100). Compressor tries to stay at or below this.")
    speed: Union[int, str] = Field(default=3, description="Quantized speed (1=slowest/best, 11=fastest).")
    level: Union[int, str] = Field(default=4, description="Optimized level (0-6). Higher is smaller and slower.")
    strip_metadata: Union[bool, str] = Field(default=True, description="Strip ancillary metadata chunks (tEXt, eXIf, iCCP, etc.).")
