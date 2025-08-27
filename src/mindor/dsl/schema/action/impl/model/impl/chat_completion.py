from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonModelInferenceActionConfig

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

class ChatCompletionParamsConfig(BaseModel):
    max_output_length: Union[int, str] = Field(default=1024, description="Maximum number of tokens to generate.")
    min_output_length: Union[int, str] = Field(default=1, description="Minimum number of tokens to generate.")
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences to return.")
    do_sample: bool = Field(default=True, description="Whether to use sampling to generate diverse texts.")
    temperature: Union[float, str] = Field(default=1.0, description="Sampling temperature; higher values produce more random results.")
    top_k: Union[int, str] = Field(default=50, description="Top-K sampling; restricts sampling to the top K tokens.")
    top_p: Union[float, str] = Field(default=0.9, description="Top-p (nucleus) sampling; restricts sampling to tokens with cumulative probability >= top_p.")
    num_beams: Union[int, str] = Field(default=1, description="Number of beams to use for beam search.")
    length_penalty: Union[float, str] = Field(default=1.0, description="Length penalty applied during beam search.")
    early_stopping: bool = Field(default=True, description="Whether to stop the beam search when all beams finish generating.")
    stop_sequences: Union[List[str], str] = Field(default=None, description="List of stop sequences.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input texts to process in a single batch.")

class ChatCompletionModelActionConfig(CommonModelInferenceActionConfig):
    messages: Union[InputMessage, List[InputMessage]] = Field(..., description="Input messages to generate text from.")
    params: ChatCompletionParamsConfig = Field(default_factory=ChatCompletionParamsConfig, description="Chat completion configuration parameters.")
