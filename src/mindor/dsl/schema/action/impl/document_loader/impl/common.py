from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonDocumentLoaderActionConfig(CommonActionConfig):
    source: Union[List[str], str] = Field(..., description="Document source, or list of sources, as path, URL, upload stream, or raw bytes.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of document sources processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether chunks are emitted incrementally as they are produced.")
