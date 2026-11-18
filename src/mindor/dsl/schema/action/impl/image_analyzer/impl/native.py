from typing import Union, Literal, Annotated
from pydantic import Field
from .common import CommonImageAnalyzerActionConfig, ImageAnalyzerMetric

class NativeImageAnalyzerMetric(ImageAnalyzerMetric):
    BRIGHTNESS    = "brightness"
    CONTRAST      = "contrast"
    EXPOSURE      = "exposure"
    DARKNESS      = "darkness"
    SHARPNESS     = "sharpness"
    NOISE         = "noise"
    FLAT_REGIONS  = "flat-regions"
    PALETTE       = "palette"
    COLOR_VARIETY = "color-variety"

class BrightnessImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.BRIGHTNESS]

class ContrastImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.CONTRAST]

class ExposureImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.EXPOSURE]
    shadow_threshold: Union[int, str] = Field(default=16, description="Pixel value (0-255) below which a pixel counts as clipped-shadow.")
    highlight_threshold: Union[int, str] = Field(default=239, description="Pixel value (0-255) above which a pixel counts as clipped-highlight.")

class DarknessImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.DARKNESS]
    dark_threshold: Union[int, str] = Field(default=32, description="Luma value (0-255) below which a pixel counts as dark.")
    block_size: Union[int, str] = Field(default=8, description="Side length in pixels of the square blocks used to compute dark-region flatness (2-64).")
    flat_std_threshold: Union[float, str] = Field(default=0.6, description="Luma standard-deviation threshold identifying flat blocks within the dark region.")

class SharpnessImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.SHARPNESS]
    blur_threshold: Union[float, int, str] = Field(default=100.0, description="Laplacian variance below which the image is flagged as blurry.")

class NoiseImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.NOISE]
    edge_quantile: Union[float, str] = Field(default=0.6, description="Gradient-magnitude quantile above which pixels are treated as edges and excluded from the noise estimate (0.0-1.0).")

class FlatRegionsImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.FLAT_REGIONS]
    block_size: Union[int, str] = Field(default=8, description="Side length in pixels of the square blocks analyzed for flatness (2-64).")
    std_threshold: Union[float, str] = Field(default=0.6, description="Luma standard-deviation threshold below which a block is classified as flat.")

class PaletteImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.PALETTE]
    bits_per_channel: Union[int, str] = Field(default=4, description="Bits retained per RGB channel when quantizing the image for palette counting (1-8).")
    coverage: Union[float, str] = Field(default=0.95, description="Fraction of pixels the counted palette must cover (0.0-1.0); the reported count is the smallest palette reaching this coverage.")
    top_k: Union[int, str] = Field(default=8, description="Number of dominant colours returned in order of pixel share.")

class ColorVarietyImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[NativeImageAnalyzerMetric.COLOR_VARIETY]
    vivid_saturation: Union[float, str] = Field(default=0.6, description="Saturation threshold (0.0-1.0) above which a pixel counts as vivid.")
    vivid_value: Union[float, str] = Field(default=0.4, description="Value/brightness threshold (0.0-1.0) above which a pixel counts as vivid.")
    hue_bins: Union[int, str] = Field(default=12, description="Number of hue bins used to count distinct hue bands (1-36).")
    hue_bin_min_share: Union[float, str] = Field(default=0.01, description="Minimum share of vivid pixels a hue bin must hold to count as a distinct band (0.0-1.0).")

NativeImageAnalyzerActionConfig = Annotated[
    Union[
        BrightnessImageAnalyzerActionConfig,
        ContrastImageAnalyzerActionConfig,
        ExposureImageAnalyzerActionConfig,
        DarknessImageAnalyzerActionConfig,
        SharpnessImageAnalyzerActionConfig,
        NoiseImageAnalyzerActionConfig,
        FlatRegionsImageAnalyzerActionConfig,
        PaletteImageAnalyzerActionConfig,
        ColorVarietyImageAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
