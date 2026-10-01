from typing import Union, Optional, List
from pydantic import BaseModel, Field
from .common import CommonImageToTextModelActionConfig

class HuggingfaceImageToTextParamsConfig(BaseModel):
    do_sample: bool = Field(default=True, description="Whether sampling is used to produce diverse outputs.")
    temperature: Union[float, str] = Field(default=1.0, description="Sampling temperature; higher values produce more random outputs.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling cutoff; restricts sampling to the K most likely tokens.")
    top_p: Union[float, str] = Field(default=0.9, description="Nucleus (top-p) sampling threshold, from 0.0 to 1.0.")
    num_beams: Union[int, str] = Field(default=1, description="Number of beams used in beam search.")
    length_penalty: Union[float, str] = Field(default=1.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether beam search stops once all beams finish generating.")

class HuggingfaceImageToTextModelActionConfig(CommonImageToTextModelActionConfig):
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens accepted per input prompt.")
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens generated; unset uses the model's configured limit.")
    min_output_length: Union[int, str] = Field(default=1, description="Minimum number of tokens generated before generation may stop.")
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences returned per input.")
    stop_sequences: Optional[Union[str, List[str]]] = Field(default=None, description="Sequences that terminate generation when produced.")
    params: HuggingfaceImageToTextParamsConfig = Field(default_factory=HuggingfaceImageToTextParamsConfig, description="Sampling and decoding parameters used for generation.")
