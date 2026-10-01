from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonImageToTextModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images the model generates text for.")
    prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Text prompt paired with each input image.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether generated tokens are emitted incrementally as they are produced.")
