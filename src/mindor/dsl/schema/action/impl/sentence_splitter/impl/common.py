from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonSentenceSplitterActionConfig(CommonActionConfig):
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts to split into sentences.")
    min_chunk_length: Union[int, str] = Field(default=0, description="Minimum characters per emitted chunk; short sentences are merged forward until the length is met. 0 emits every sentence.")
    max_chunk_length: Optional[Union[int, str]] = Field(default=None, description="Maximum characters per emitted chunk; longer sentences are hard-split at the nearest whitespace or the character limit.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether chunks are emitted incrementally as they are produced.")
