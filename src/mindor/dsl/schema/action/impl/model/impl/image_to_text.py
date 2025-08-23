from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelInferenceActionConfig

class ImageToTextParamsConfig(BaseModel):
    batch_size: Union[int, str] = Field(default=1, description="Number of input images to process in a single batch.")

class ImageToTextModelActionConfig(CommonModelInferenceActionConfig):
    image: Union[Union[str, List[str]], str] = Field(..., description="")
    prompt: Optional[Union[str, Union[str, List[str]]]] = Field(default=None, description="Input prompt to generate text from.")
    params: ImageToTextParamsConfig = Field(default_factory=ImageToTextParamsConfig, description="Image to text configuration parameters.")
