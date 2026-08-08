from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonMediaInspectorActionConfig(CommonActionConfig):
    media: Union[str, List[str]] = Field(..., description="Media source(s) to inspect.")
    return_raw: Union[bool, str] = Field(default=True, description="Whether to include the raw driver output.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources per batch.")
