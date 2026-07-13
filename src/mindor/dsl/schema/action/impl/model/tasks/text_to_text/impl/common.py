from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelActionConfig

class TextToTextParamsConfig(BaseModel):
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens to generate. None uses the model/backend's configured limit.")
    min_output_length: Union[int, str] = Field(default=1, description="Minimum tokens to generate.")
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences to return.")
    do_sample: bool = Field(default=False, description="Whether to use sampling; seq2seq models typically decode with beam search.")
    temperature: Union[float, str] = Field(default=1.0, description="Sampling temperature; only used when do_sample is true.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling; only used when do_sample is true.")
    top_p: Union[float, str] = Field(default=1.0, description="Top-p (nucleus) sampling; only used when do_sample is true.")
    num_beams: Union[int, str] = Field(default=4, description="Number of beams for beam search.")
    length_penalty: Union[float, str] = Field(default=1.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether to stop beam search when all beams finish generating.")

class TextToTextModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Source text to translate, summarize, or otherwise transform.")
    batch_size: Union[int, str] = Field(default=1, description="Input texts per batch.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens per input text.")
    stop_sequences: Optional[Union[str, List[str]]] = Field(default=None, description="Stop sequence(s) that terminate generation.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream generated tokens as they are produced.")
    params: TextToTextParamsConfig = Field(default_factory=TextToTextParamsConfig, description="Text-to-text parameters.")
