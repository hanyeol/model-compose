from typing import Union, Optional, List, Literal
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class MusicScoreRenderFormat(str, Enum):
    SVG = "svg"
    PDF = "pdf"
    PNG = "png"

class MusicScoreRenderMarginConfig(BaseModel):
    top: Union[float, str] = Field(default=50.0, description="Top page margin in Verovio units.")
    right: Union[float, str] = Field(default=50.0, description="Right page margin in Verovio units.")
    bottom: Union[float, str] = Field(default=50.0, description="Bottom page margin in Verovio units.")
    left: Union[float, str] = Field(default=50.0, description="Left page margin in Verovio units.")

class CommonMusicScoreRendererActionConfig(CommonActionConfig):
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of score sources rendered per batch.")
