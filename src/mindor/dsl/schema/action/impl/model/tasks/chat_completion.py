from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
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
    type: Literal["function"] = Field(default="function", description="Tool call type.")
    function: Dict[str, Any] = Field(default_factory=dict, description="Function name and arguments.")

class ChatCompletionMessage(ChatMessage):
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Tool calls requested by the model.")

InputMessage: TypeAlias = Union[ChatMessage, Dict[str, Any]]

class ChatCompletionModelActionConfig(CommonModelActionConfig):
    messages: Union[InputMessage, List[InputMessage]] = Field(..., description="Input messages to generate chat response from.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input texts to process in a single batch.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens per input text.")
    stop_sequences: Optional[Union[str, List[str]]] = Field(default=None, description="List of stop sequences.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream generated tokens as they are produced.")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Chat completion configuration parameters.")
    tools: Optional[Union[List[str], List[ModelTool]]] = Field(default=None, description="Tools for this action: either names referencing the component's catalog, or inline ModelTool definitions. None exposes all tools from the catalog.")
