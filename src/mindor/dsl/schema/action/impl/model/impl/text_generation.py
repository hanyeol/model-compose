from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextGenerationParamsConfig(BaseModel):
    max_output_length: Union[int, str] = Field(default=1024, description="Maximum number of tokens to generate.")
    min_output_length: Union[int, str] = Field(default=1, description="Minimum number of tokens to generate.")
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences to return.")
    do_sample: bool = Field(default=True, description="Whether to use sampling to generate diverse texts.")
    temperature: Union[float, str] = Field(default=0.7, description="Sampling temperature; higher values produce more random results.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling; restricts sampling to the top K tokens.")
    top_p: Union[float, str] = Field(default=0.9, description="Top-p (nucleus) sampling; restricts sampling to tokens with cumulative probability >= top_p.")
    num_beams: Union[int, str] = Field(default=1, description="Number of beams to use for beam search.")
    length_penalty: Union[float, str] = Field(default=1.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether to stop the beam search when all beams finish generating.")

class TextGenerationModelActionConfig(CommonModelActionConfig):
    text: Union[Union[str, List[str]], str] = Field(..., description="Input text to generate text from.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input texts to process in a single batch.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens per input text.")
    stop_sequences: Union[List[str], str] = Field(default=None, description="List of stop sequences.")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Text generation configuration parameters.")
