from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonMediaInspectorActionConfig(CommonActionConfig):
    media: Union[str, List[str]] = Field(..., description="Media source or list of sources to inspect.")
    return_raw: Union[bool, str] = Field(default=True, description="Whether the raw driver output is included in the result.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources processed per batch.")
