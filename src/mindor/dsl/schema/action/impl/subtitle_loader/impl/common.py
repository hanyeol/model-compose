from typing import Union, Optional
from pydantic import Field
from ...common import CommonActionConfig

class CommonSubtitleLoaderActionConfig(CommonActionConfig):
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of subtitle sources processed per batch.")
