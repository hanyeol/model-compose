from typing import Union, Optional, List, Literal, Annotated
from pydantic import Field
from .common import CommonModelTokenizerActionConfig, ModelTokenizerMethod

class TextModelTokenizerEncodeActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.ENCODE]
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts to tokenize.")
    max_length: Optional[Union[int, str]] = Field(default=None, description="Maximum token length per encoded sequence.")
    padding: Union[bool, str] = Field(default=False, description="Whether encoded sequences are padded to `max_length`.")
    truncation: Union[bool, str] = Field(default=False, description="Whether encoded sequences are truncated to `max_length`.")
    additional_returns: Union[List[str], str] = Field(default_factory=list, description="Extra fields included in each result beyond `input_ids` and `attention_mask`.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts processed per batch.")

class TextModelTokenizerDecodeActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.DECODE]
    token_ids: Union[List[int], List[List[int]], str] = Field(..., description="Token ID sequence or sequences to decode back to text.")
    skip_special_tokens: Union[bool, str] = Field(default=True, description="Whether special tokens are omitted from the decoded text.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of token ID sequences processed per batch.")

class TextModelTokenizerCountActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.COUNT]
    text: Union[str, List[str]] = Field(..., description="Input text or list of texts whose tokens are counted.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts processed per batch.")

TextModelTokenizerActionConfig = Annotated[
    Union[
        TextModelTokenizerEncodeActionConfig,
        TextModelTokenizerDecodeActionConfig,
        TextModelTokenizerCountActionConfig
    ],
    Field(discriminator="method")
]
