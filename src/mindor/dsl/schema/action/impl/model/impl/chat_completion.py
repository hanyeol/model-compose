from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .text_generation import CommonModelActionConfig, TextGenerationParamsConfig

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message sender.")
    content: str = Field(..., description="Text content of the chat message.")

class ToolCall(BaseModel):
    role: str = Field(default="assistant", description="Role for tool calls.")
    name: str = Field(..., description="Tool name.")
    call_id: str = Field(..., description="Tool call identifier.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool function.")

class ToolResult(BaseModel):
    role: str = Field(default="tool", description="Role for tool responses.")
    call_id: str = Field(..., description="Tool call identifier.")
    name: Optional[str] = Field(default=None, description="Tool name.")
    content: Optional[Any] = Field(default=None, description="Tool execution result.")
    error: Optional[str] = Field(default=None, description="Error message if tool execution failed.")

InputMessage: TypeAlias = Union[ToolResult, ToolCall, ChatMessage]

class ChatCompletionModelActionConfig(CommonModelActionConfig):
    messages: Union[InputMessage, List[InputMessage]] = Field(..., description="Input messages to generate chat response from.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input texts to process in a single batch.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens per input text.")
    stop_sequences: Union[List[str], str] = Field(default=None, description="List of stop sequences.")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Chat completion configuration parameters.")
