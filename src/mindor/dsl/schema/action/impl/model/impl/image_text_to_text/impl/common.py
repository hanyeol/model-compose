from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelActionConfig

class ImageTextToTextParamsConfig(BaseModel):
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens to generate. None lets the model use its own configured limit.")
    min_output_length: Union[int, str] = Field(default=1, description="Minimum number of tokens to generate.")
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences to return.")
    do_sample: bool = Field(default=True, description="Whether to use sampling to generate diverse text.")
    temperature: Union[float, str] = Field(default=1.0, description="Sampling temperature; higher values produce more random results.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling; restricts sampling to the top K tokens.")
    top_p: Union[float, str] = Field(default=0.9, description="Top-p (nucleus) sampling; restricts sampling to tokens with cumulative probability >= top_p.")
    num_beams: Union[int, str] = Field(default=1, description="Number of beams to use for beam search.")
    length_penalty: Union[float, str] = Field(default=1.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether to stop the beam search when all beams finish generating.")

class ImageTextToTextModelActionConfig(CommonModelActionConfig):
    image: Union[Union[str, List[str]], str] = Field(..., description="Input image (or list of images) to feed into the vision-language model.")
    prompt: Union[str, List[str]] = Field(..., description="Text prompt paired with the input image.")
    system_prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Optional system prompt applied before the user prompt.")
    batch_size: Union[int, str] = Field(default=1, description="Number of image/prompt pairs to process in a single batch.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens per input prompt.")
    stop_sequences: Union[Union[str, List[str]], str] = Field(default=None, description="Stop sequence(s) that terminate generation.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream generated tokens as they are produced.")
    params: ImageTextToTextParamsConfig = Field(default_factory=ImageTextToTextParamsConfig, description="Image-text-to-text configuration parameters.")
