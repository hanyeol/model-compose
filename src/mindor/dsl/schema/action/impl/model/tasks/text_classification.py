from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextClassificationModelActionConfig(CommonModelActionConfig):
    text: Union[str, Union[str, List[str]]] = Field(..., description="Input text to classify.")
    max_input_length: Union[int, str] = Field(default=512, description="Maximum tokens per input text.")
    return_probabilities: Union[bool, str] = Field(default=False, description="Whether to return class probabilities per prediction.")
    batch_size: Union[int, str] = Field(default=32, description="Input texts per batch.")
