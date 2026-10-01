from typing import Union, Optional
from pydantic import BaseModel, Field
from ..common import CommonImageToTextModelActionConfig

class RapidOcrImageToTextParamsConfig(BaseModel):
    text_score: Union[float, str] = Field(default=0.5, description="Minimum recognition confidence; regions below this are dropped.")
    box_thresh: Union[float, str] = Field(default=0.5, description="Detection score threshold applied when forming text boxes.")
    unclip_ratio: Union[float, str] = Field(default=1.6, description="Ratio used to expand detected polygons before recognition.")
    use_cls: Union[bool, str] = Field(default=True, description="Whether the angle classifier corrects rotated text before recognition.")

class RapidOcrImageToTextModelActionConfig(CommonImageToTextModelActionConfig):
    return_polygons: Union[bool, str] = Field(default=False, description="If true, emit a structured dict with per-text polygons and scores; otherwise emit joined text as a string.")
    params: RapidOcrImageToTextParamsConfig = Field(default_factory=RapidOcrImageToTextParamsConfig, description="RapidOCR detection and recognition parameters.")
