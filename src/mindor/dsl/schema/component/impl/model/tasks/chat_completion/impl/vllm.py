from typing import Literal, List, Dict, Optional, Any
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import CommonChatCompletionModelComponentConfig
from ...common import ModelDriver
from ...base.vllm import VllmEngineOptionsConfig

class VllmChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    tool_call_parser: Optional[str] = Field(default=None, description="Parser for tool call outputs (e.g., 'hermes', 'mistral', 'llama3_json', 'pythonic').")
    tool_parser_plugin: Optional[str] = Field(default=None, description="Path to a custom tool parser plugin module registered at engine startup.")
    reasoning_parser: Optional[str] = Field(default=None, description="Parser for reasoning model outputs.")
    reasoning_config: Optional[Dict[str, Any]] = Field(default=None, description="Reasoning model settings.")
    options: Optional[VllmEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to vLLM when loading the model.")
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list, description="Actions this chat completion component exposes to workflows.")
