from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonMediaDownloaderActionConfig(CommonActionConfig):
    url: Union[str, List[str]] = Field(..., description="Source URL, or list of URLs, to download from.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of URLs downloaded concurrently per batch.")
