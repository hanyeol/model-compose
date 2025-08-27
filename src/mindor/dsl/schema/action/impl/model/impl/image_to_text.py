from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelInferenceActionConfig

class ImageToTextParamsConfig(BaseModel):
    max_input_length: Union[int, str] = Field(default=1024, description="Maximum number of tokens per input text.")
    max_output_length: Union[int, str] = Field(default=1024, description="Maximum number of tokens to generate.")
    min_output_length: Union[int, str] = Field(default=1, description="Minimum number of tokens to generate.")
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences to return.")
    do_sample: bool = Field(default=True, description="Whether to use sampling to generate diverse text.")
    temperature: Union[float, str] = Field(default=1.0, description="Sampling temperature; higher values produce more random results.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling; restricts sampling to the top K tokens.")
    top_p: Union[float, str] = Field(default=0.9, description="Top-p (nucleus) sampling; restricts sampling to tokens with cumulative probability >= top_p.")
    num_beams: Union[int, str] = Field(default=1, description="Number of beams to use for beam search.")
    length_penalty: Union[float, str] = Field(default=1.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether to stop the beam search when all beams finish generating.")
    stop_sequences: Union[Union[str, List[str]], str] = Field(default=None, description="Stop sequence.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images to process in a single batch.")

class ImageToTextModelActionConfig(CommonModelInferenceActionConfig):
    image: Union[Union[str, List[str]], str] = Field(..., description="Input image for text generation.")
    prompt: Optional[Union[str, Union[str, List[str]]]] = Field(default=None, description="Input prompt to generate text from.")
    params: ImageToTextParamsConfig = Field(default_factory=ImageToTextParamsConfig, description="Image to text configuration parameters.")
