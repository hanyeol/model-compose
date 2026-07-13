from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelActionConfig

class ImageToTextParamsConfig(BaseModel):
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens to generate. None uses the model's configured limit.")
    min_output_length: Union[int, str] = Field(default=1, description="Minimum tokens to generate.")
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences to return.")
    do_sample: bool = Field(default=True, description="Whether to use sampling for diverse text.")
    temperature: Union[float, str] = Field(default=1.0, description="Sampling temperature; higher values produce more random results.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling; restricts sampling to the top K tokens.")
    top_p: Union[float, str] = Field(default=0.9, description="Top-p (nucleus) sampling threshold.")
    num_beams: Union[int, str] = Field(default=1, description="Number of beams for beam search.")
    length_penalty: Union[float, str] = Field(default=1.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether to stop beam search when all beams finish generating.")

class ImageToTextModelActionConfig(CommonModelActionConfig):
    image: Union[Union[str, List[str]], str] = Field(..., description="Input image for text generation.")
    prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Optional text prompt paired with the input image.")
    batch_size: Union[int, str] = Field(default=1, description="Input images per batch.")
    max_input_length: Union[int, str] = Field(default=1024, description="Maximum tokens per input text.")
    stop_sequences: Optional[Union[str, List[str]]] = Field(default=None, description="Stop sequence.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream generated tokens as they are produced.")
    params: ImageToTextParamsConfig = Field(default_factory=ImageToTextParamsConfig, description="Image-to-text parameters.")
