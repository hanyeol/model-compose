from typing import Type, Union, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.common.model.tool import ModelTool
from .text_generation import CommonModelActionConfig, TextGenerationParamsConfig

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message sender (e.g., user, assistant, system, tool).")
    content: Optional[Any] = Field(default=None, description="Content of the chat message.")

    model_config = { "extra": "allow" }

class ToolCall(BaseModel):
    id: str = Field(..., description="Identifier of this tool call, echoed back in the tool response.")
    name: str = Field(..., description="Name of the tool the model wants to invoke.")
    arguments: Union[str, Dict[str, Any]] = Field(default_factory=dict, description="Arguments passed to the tool, either as a JSON string or a decoded object.")

class ChatCompletionMessage(ChatMessage):
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Tool calls requested by the model on this message.")

InputMessage: TypeAlias = Union[ChatMessage, Dict[str, Any]]

class ChatCompletionModelActionConfig(CommonModelActionConfig):
    messages: Union[InputMessage, List[InputMessage]] = Field(..., description="Input chat messages the model generates a response for.")
    tools: Optional[Union[List[str], List[ModelTool]]] = Field(default=None, description="Tools the model may call during this action.")
    max_input_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens accepted per input message.")
    max_output_length: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens generated; unset uses the model or backend's configured limit.")
    min_output_length: Union[int, str] = Field(default=1, description="Minimum number of tokens generated before generation may stop.")
    num_return_sequences: Union[int, str] = Field(default=1, description="Number of generated sequences returned per input.")
    stop_sequences: Optional[Union[str, List[str]]] = Field(default=None, description="Sequences that terminate generation when produced.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input messages processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether generated tokens are emitted incrementally as they are produced.")
    params: TextGenerationParamsConfig = Field(default_factory=TextGenerationParamsConfig, description="Sampling and decoding parameters used for chat completion.")
