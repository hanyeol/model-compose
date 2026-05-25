from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonModelTokenizerActionConfig, ModelTokenizerMethod

class TextModelTokenizerEncodeActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.ENCODE]
    text: str = Field(..., description="Input text to tokenize.")
    max_length: Optional[Union[int, str]] = Field(default=None, description="Maximum token length.")
    padding: Union[bool, str] = Field(default=False, description="Whether to pad to max_length.")
    truncation: Union[bool, str] = Field(default=False, description="Whether to truncate to max_length.")

class TextModelTokenizerDecodeActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.DECODE]
    token_ids: Union[List[int], str] = Field(..., description="Token IDs to decode.")
    skip_special_tokens: Union[bool, str] = Field(default=True, description="Whether to skip special tokens in output.")

class TextModelTokenizerCountActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.COUNT]
    text: str = Field(..., description="Input text to count tokens for.")

TextModelTokenizerActionConfig = Annotated[
    Union[
        TextModelTokenizerEncodeActionConfig,
        TextModelTokenizerDecodeActionConfig,
        TextModelTokenizerCountActionConfig
    ],
    Field(discriminator="method")
]
