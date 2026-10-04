from typing import Union, List, Any
from pydantic import BaseModel, Field
from .common import CommonModelActionConfig

class VideoTextScoringParamsConfig(BaseModel):
    return_logit: Union[bool, str] = Field(default=False, description="Whether the raw logit (cosine × logit_scale) is included alongside the cosine score.")
    return_softmax: Union[bool, str] = Field(default=True, description="Whether softmax probabilities are included when scoring produces two or more pairs.")

class VideoTextScoringModelActionConfig(CommonModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to score; a single video's frames, a list of frames, a list of per-video frame batches, or a stream of batches.")
    text: Union[str, List[str]] = Field(..., description="Input caption or list of captions to score against the video(s).")
    batch_size: Union[int, str] = Field(default=1, description="Number of scoring jobs processed per batch.")
    params: VideoTextScoringParamsConfig = Field(default_factory=VideoTextScoringParamsConfig, description="Scoring output options.")
