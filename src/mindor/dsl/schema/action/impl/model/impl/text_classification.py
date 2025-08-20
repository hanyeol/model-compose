from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelInferenceActionConfig

class TextClassificationParamsConfig(BaseModel):
    return_probabilities: Union[bool, str] = Field(default=False, description="Whether to return class probabilities for each prediction.")
    batch_size: Union[int, str] = Field(default=32, description="Number of input texts to process in a single batch.")

class TextClassificationModelActionConfig(CommonModelInferenceActionConfig):
    text: Union[str, Union[str, List[str]]] = Field(..., description="Input text to classify.")
    params: TextClassificationParamsConfig = Field(default_factory=TextClassificationParamsConfig, description="Text classification configuration parameters.")
