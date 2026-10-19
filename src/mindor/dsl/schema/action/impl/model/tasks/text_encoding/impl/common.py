from typing import List, Optional, Union
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class TextEncodingParamsConfig(BaseModel):
    layer: Union[int, str] = Field(default=-1, description="Transformer layer index to read hidden states from; negative values index from the top.")
    add_special_tokens: Union[bool, str] = Field(default=False, description="Whether the tokenizer inserts BOS/EOS markers around the input.")
    max_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens accepted per input text; unset uses the tokenizer's default.")

class TextEncodingModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts to encode.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input texts processed per batch.")
    params: TextEncodingParamsConfig = Field(default_factory=TextEncodingParamsConfig, description="Text encoding parameters.")
