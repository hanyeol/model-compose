from typing import Union, Optional, List
from pydantic import Field
from .common import CommonTextGenerationModelActionConfig, TextGenerationParamsConfig

class HuggingfaceTextGenerationModelActionConfig(CommonTextGenerationModelActionConfig):
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences returned per input.")
    stop_sequences: Optional[Union[str, List[str]]] = Field(default=None, description="Sequences that terminate generation when produced.")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Sampling and decoding parameters used for text generation.")
