from typing import Union, Optional, List, Literal, Annotated
from pydantic import Field
from .common import CommonModelTokenizerActionConfig, ModelTokenizerMethod

class TextModelTokenizerEncodeActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.ENCODE]
    text: Union[str, List[str]] = Field(..., description="Input text(s) to tokenize.")
    max_length: Optional[Union[int, str]] = Field(default=None, description="Maximum token length.")
    padding: Union[bool, str] = Field(default=False, description="Whether to pad to max_length.")
    truncation: Union[bool, str] = Field(default=False, description="Whether to truncate to max_length.")
    additional_returns: Union[List[str], str] = Field(default_factory=list, description="Additional fields to include in each result, on top of input_ids and attention_mask.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts to process in a single batch.")

class TextModelTokenizerDecodeActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.DECODE]
    token_ids: Union[List[int], List[List[int]], str] = Field(..., description="Token ID(s) to decode.")
    skip_special_tokens: Union[bool, str] = Field(default=True, description="Whether to skip special tokens in output.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input token ID lists to process in a single batch.")

class TextModelTokenizerCountActionConfig(CommonModelTokenizerActionConfig):
    method: Literal[ModelTokenizerMethod.COUNT]
    text: Union[str, List[str]] = Field(..., description="Input text(s) to count tokens for.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input texts to process in a single batch.")

TextModelTokenizerActionConfig = Annotated[
    Union[
        TextModelTokenizerEncodeActionConfig,
        TextModelTokenizerDecodeActionConfig,
        TextModelTokenizerCountActionConfig
    ],
    Field(discriminator="method")
]
