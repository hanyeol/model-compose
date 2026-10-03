from typing import Union, List
from pydantic import BaseModel, Field
from .common import CommonModelActionConfig

class ImageTextScoringParamsConfig(BaseModel):
    return_logit: Union[bool, str] = Field(default=False, description="Whether the raw logit (cosine × logit_scale) is included alongside the cosine score.")
    return_softmax: Union[bool, str] = Field(default=True, description="Whether softmax probabilities are included when scoring produces two or more pairs.")

class ImageTextScoringModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images (path, URL, or base64) to score against text.")
    text: Union[str, List[str]] = Field(..., description="Input caption or list of captions to score against the image(s).")
    batch_size: Union[int, str] = Field(default=8, description="Number of pairs processed per forward pass.")
    params: ImageTextScoringParamsConfig = Field(default_factory=ImageTextScoringParamsConfig, description="Scoring output options.")
