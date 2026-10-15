from typing import Union, Optional, List
from pydantic import Field
from .common import (
    CommonMusicScoreRendererActionConfig,
    MusicScoreRendererFormat,
    MusicScoreRendererMarginConfig,
)

class VerovioMusicScoreRendererActionConfig(CommonMusicScoreRendererActionConfig):
    source: Union[List[str], str] = Field(..., description="MusicXML source, or list of sources, as path, upload stream, or raw bytes.")
    format: Union[MusicScoreRendererFormat, str] = Field(default=MusicScoreRendererFormat.SVG, description="Output format for each rendered page.")
    page_width: Union[float, str] = Field(default=2100.0, description="Page width in Verovio units (1 unit ≈ 0.1mm).")
    page_height: Union[float, str] = Field(default=2970.0, description="Page height in Verovio units (1 unit ≈ 0.1mm).")
    scale: Union[int, str] = Field(default=100, description="Rendering scale percent; 100 is Verovio's default size.")
    margin: Optional[Union[MusicScoreRendererMarginConfig, float, str]] = Field(default=None, description="Page margins; a scalar applies to all four sides.")
    dpi: Union[int, str] = Field(default=150, description="Resolution of PNG rasterization. Ignored for `svg` and `pdf`.")
