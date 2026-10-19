from typing import Union, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonFaceEmotionClassificationModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input face crop image or list of face crops to classify.")
    return_probabilities: Union[bool, str] = Field(default=True, description="Whether per-class probabilities are included in the result.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
