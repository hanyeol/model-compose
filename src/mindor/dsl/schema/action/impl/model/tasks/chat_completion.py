from typing import Type, Union, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.common.model.tool import ModelTool
from .text_generation import CommonModelActionConfig, TextGenerationParamsConfig

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message sender.")
    content: Optional[Any] = Field(default=None, description="Content of the chat message.")

    model_config = { "extra": "allow" }

class ToolCall(BaseModel):
    id: str = Field(..., description="Tool call identifier.")
    name: str = Field(..., description="Tool name to invoke.")
    arguments: Union[str, Dict[str, Any]] = Field(default_factory=dict, description="Tool arguments as JSON string or decoded dict.")

class ChatCompletionMessage(ChatMessage):
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Tool calls requested by the model.")

InputMessage: TypeAlias = Union[ChatMessage, Dict[str, Any]]

class ChatCompletionModelActionConfig(CommonModelActionConfig):
    messages: Union[InputMessage, List[InputMessage]] = Field(..., description="Input messages to generate chat response from.")
    batch_size: Union[int, str] = Field(default=1, description="Input texts per batch.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum tokens per input text.")
    stop_sequences: Optional[Union[str, List[str]]] = Field(default=None, description="List of stop sequences.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream generated tokens as they are produced.")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Chat completion parameters.")
    tools: Optional[Union[List[str], List[ModelTool]]] = Field(default=None, description="Tools available for this action.")
