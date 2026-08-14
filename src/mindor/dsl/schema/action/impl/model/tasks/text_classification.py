from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelActionConfig

class TextClassificationModelActionConfig(CommonModelActionConfig):
    text: Union[str, Union[str, List[str]]] = Field(..., description="Input text or list of texts to classify.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens accepted per input text; unset uses the tokenizer's default.")
    return_probabilities: Union[bool, str] = Field(default=False, description="Whether class probabilities are included in each prediction.")
    batch_size: Union[int, str] = Field(default=32, description="Number of input texts processed per batch.")
