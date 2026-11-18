from typing import Union, Literal, Annotated
from pydantic import Field
from .common import CommonImageAnalyzerActionConfig, ImageAnalyzerMetric

class OpenCvImageAnalyzerMetric(ImageAnalyzerMetric):
    GRADIENT       = "gradient"
    EDGE_STRUCTURE = "edge-structure"
    TEXTURE        = "texture"
    LIT_STRUCTURE  = "lit-structure"

class GradientImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[OpenCvImageAnalyzerMetric.GRADIENT]
    gradient_min: Union[float, str] = Field(default=2.0, description="Lower Sobel-magnitude bound of the 'gentle gradient' band (pixels below are treated as flat, excluded).")
    gradient_max: Union[float, str] = Field(default=20.0, description="Upper Sobel-magnitude bound of the 'gentle gradient' band (pixels above are treated as edges, excluded).")
    curvature_threshold: Union[float, str] = Field(default=1.0, description="Second-derivative magnitude below which a gentle-gradient pixel counts as 'clean' (smoothly curving).")

class EdgeStructureImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[OpenCvImageAnalyzerMetric.EDGE_STRUCTURE]
    edge_threshold: Union[float, str] = Field(default=80.0, description="Sobel gradient-magnitude threshold above which a pixel is counted as an edge.")
    axis_tolerance_degrees: Union[float, str] = Field(default=4.0, description="Angular tolerance in degrees around 0deg/90deg within which an edge counts as axis-aligned.")
    orientation_bins: Union[int, str] = Field(default=18, description="Number of orientation bins used to compute edge-direction entropy (2-180).")

class TextureImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[OpenCvImageAnalyzerMetric.TEXTURE]
    fine_kernel: Union[int, str] = Field(default=3, description="Median-blur kernel size (odd, >=3) that removes fine-scale texture; larger values smooth more.")
    mid_kernel: Union[int, str] = Field(default=7, description="Median-blur kernel size (odd, >=3) that removes mid-scale texture.")
    coarse_kernel: Union[int, str] = Field(default=15, description="Median-blur kernel size (odd, >=3) that removes coarse-scale texture.")
    detail_threshold: Union[float, str] = Field(default=6.0, description="Absolute high-pass residual above which a pixel counts as carrying detail at the target scale.")

class LitStructureImageAnalyzerActionConfig(CommonImageAnalyzerActionConfig):
    metric: Literal[OpenCvImageAnalyzerMetric.LIT_STRUCTURE]
    lit_threshold: Union[int, str] = Field(default=128, description="Luma value (0-255) above which a pixel is considered lit.")
    ink_threshold: Union[int, str] = Field(default=96, description="Luma value (0-255) below which a pixel is considered ink (dark mark on light ground).")
    peak_window: Union[int, str] = Field(default=3, description="Dilation window side length (odd, >=3) used to detect local-maxima peaks.")
    smooth_tolerance: Union[float, str] = Field(default=8.0, description="Luma difference below which a lit/ink pixel counts as shading smoothly with its neighbourhood.")

OpenCvImageAnalyzerActionConfig = Annotated[
    Union[
        GradientImageAnalyzerActionConfig,
        EdgeStructureImageAnalyzerActionConfig,
        TextureImageAnalyzerActionConfig,
        LitStructureImageAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
