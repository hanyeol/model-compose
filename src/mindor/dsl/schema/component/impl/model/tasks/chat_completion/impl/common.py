from typing import Literal, Optional, List
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.common.model.tool import ModelTool
from ...common import LanguageModelComponentConfig, ModelTaskType

class ToolCallBodyFormat(str, Enum):
    JSON     = "json"
    PYTHONIC = "pythonic"

class ToolCallNameMarker(BaseModel):
    """Locates the tool name as a literal between two markers in the call body (not as a JSON field)."""
    prefix: str = Field(..., description="Literal string immediately before the tool name in the body.")
    suffix: str = Field(..., description="Literal string immediately after the tool name in the body.")

class ToolCallArgumentsMarker(BaseModel):
    """Locates tool arguments inside a wrapper (e.g., a fenced code block) rather than as the whole body."""
    open: str = Field(..., description="Literal string that opens the arguments wrapper (e.g., '```json\\n').")
    close: str = Field(..., description="Literal string that closes the arguments wrapper (e.g., '\\n```').")

class ToolCallParserConfig(BaseModel):
    batch_start_tag: Optional[str] = Field(default=None, description="Optional outer marker that opens a batch of tool calls (e.g., DeepSeek's '<｜tool_calls_begin｜>').")
    batch_end_tag: Optional[str] = Field(default=None, description="Optional outer marker that closes a batch of tool calls.")
    start_tag: str = Field(..., description="Literal marker that opens a single tool call in the model output (e.g., '<tool_call>').")
    end_tag: Optional[str] = Field(default=None, description="Literal marker that closes a single tool call; omit to parse one JSON/pythonic value immediately following the start marker.")
    format: ToolCallBodyFormat = Field(default=ToolCallBodyFormat.JSON, description="Body syntax between the markers (json or pythonic).")
    name_key: str = Field(default="name", description="JSON field name that holds the tool name. Ignored when name_marker is set.")
    arguments_key: str = Field(default="arguments", description="JSON field name that holds the tool arguments. Ignored when arguments_marker is set.")
    name_marker: Optional[ToolCallNameMarker] = Field(default=None, description="Locate the tool name as a literal between two markers in the body instead of reading a JSON field.")
    arguments_marker: Optional[ToolCallArgumentsMarker] = Field(default=None, description="Locate the arguments inside a wrapper (e.g., fenced code block) instead of treating the whole body as the arguments payload.")

    @model_validator(mode="after")
    def validate_keys_for_pythonic_format(self):
        if self.format == ToolCallBodyFormat.PYTHONIC and (self.name_key != "name" or self.arguments_key != "arguments"):
            raise ValueError("name_key and arguments_key have no effect when format is 'pythonic'.")
        return self

    @model_validator(mode="after")
    def validate_markers_for_pythonic_format(self):
        if self.format == ToolCallBodyFormat.PYTHONIC and (self.name_marker is not None or self.arguments_marker is not None):
            raise ValueError("name_marker and arguments_marker are only supported when format is 'json'.")
        return self

    @model_validator(mode="after")
    def validate_batch_tags_paired(self):
        if (self.batch_start_tag is None) != (self.batch_end_tag is None):
            raise ValueError("batch_start_tag and batch_end_tag must be set together.")
        return self

class CommonChatCompletionModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.CHAT_COMPLETION]
    chat_template: Optional[str] = Field(default=None, description="Inline Jinja chat template string, overriding the tokenizer default.")
    tools: Optional[List[ModelTool]] = Field(default=None, description="Catalog of tools this component exposes for tool calling.")
    tool_call_parser: Optional[ToolCallParserConfig] = Field(default=None, description="Rules for extracting tool calls from raw model output.")
