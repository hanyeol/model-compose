from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonSentenceSplitterActionConfig(CommonActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text(s) to split into sentences.")
    min_chunk_length: Union[int, str] = Field(default=0, description="Minimum characters per emitted chunk. Sentences shorter than this are joined with the next sentence until the length is met (0 = emit every sentence).")
    max_chunk_length: Optional[Union[int, str]] = Field(default=None, description="Maximum characters per emitted chunk. Sentences longer than this are hard-split at the nearest whitespace or at the character limit.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream chunks one by one instead of returning a full list.")
