from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonImageCompressorActionConfig(CommonActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input images processed per batch.")
    strip_metadata: Union[bool, str] = Field(default=True, description="Whether ancillary PNG metadata chunks (tEXt, eXIf, iCCP, etc.) are removed from the output.")
