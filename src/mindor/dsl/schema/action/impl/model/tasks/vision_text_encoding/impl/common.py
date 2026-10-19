from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class VisionTextEncodingParamsConfig(BaseModel):
    layer: Union[int, str] = Field(default=-1, description="Transformer layer index to read hidden states from; negative values index from the top.")
    add_special_tokens: Union[bool, str] = Field(default=False, description="Whether the tokenizer inserts BOS/EOS markers around the input.")
    max_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens accepted per input prompt; unset uses the tokenizer's default.")

class VisionTextEncodingModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts to encode.")
    images: Optional[Union[str, List[str], List[List[str]]]] = Field(default=None, description="Reference image(s) accompanying each prompt; a list per prompt for multi-image inputs.")
    frames: Optional[Union[Any, List[Any], List[List[Any]]]] = Field(default=None, description="Reference video frames accompanying each prompt; outer list is per prompt, inner list is the frame sequence (sampled by the caller, e.g. 2 fps for R2V).")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: VisionTextEncodingParamsConfig = Field(default_factory=VisionTextEncodingParamsConfig, description="Vision-text encoding parameters.")
