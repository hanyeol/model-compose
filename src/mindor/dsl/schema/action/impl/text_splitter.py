from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class TextSplitterActionConfig(CommonActionConfig):
    text: str = Field(..., description="Input text to be split.")
    separators: Optional[List[str]] = Field(default=None, description="Separators used for splitting.")
    chunk_size: Union[int, str] = Field(default=1000, description="Maximum number of characters per chunk.")
    chunk_overlap: Union[int, str] = Field(default=200, description="Number of overlapping characters between chunks.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream chunks one by one instead of returning full list.")
