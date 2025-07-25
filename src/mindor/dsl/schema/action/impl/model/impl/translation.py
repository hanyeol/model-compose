from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TranslationParamsConfig(BaseModel):
    max_input_length: Union[int, str] = Field(default=1024, description="Maximum number of tokens per input text.")
    max_output_length: Union[int, str] = Field(default=256, description="The maximum number of tokens to generate.")
    min_output_length: Union[int, str] = Field(default=10, description="The minimum number of tokens to generate.")
    num_beams: Union[int, str] = Field(default=4, description="Number of beams to use for beam search.")
    length_penalty: Union[float, str] = Field(default=1.0, description="Length penalty applied during beam search.")
    batch_size: Union[int, str] = Field(default=32, description="Number of input texts to process in a single batch.")

class TranslationModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text to translate.")
    params: TranslationParamsConfig = Field(default_factory=TranslationParamsConfig, description="Translation configuration parameters.")
