from typing import Literal, Optional, List
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.common.model.tool import ModelTool
from ...common import LanguageModelComponentConfig, ModelTaskType

class ToolCallBodyFormat(str, Enum):
    JSON     = "json"
    PYTHONIC = "pythonic"
    XML      = "xml"

class ToolCallNameMarker(BaseModel):
    """Locates the tool name as a literal between two markers in the call body (not as a JSON field)."""
    prefix: str = Field(..., description="Literal string immediately before the tool name in the body.")
    suffix: str = Field(..., description="Literal string immediately after the tool name in the body.")

class ToolCallArgumentsMarker(BaseModel):
    """Locates tool arguments inside the call body.

    Two shapes are supported:
      * **wrapper** — the arguments live as one JSON payload between a prefix/suffix pair
        (e.g., DeepSeek's ```` ```json\\n{...}\\n``` ````). Set ``prefix`` and ``suffix``.
      * **repeat** — the arguments appear as repeating ``<key>value</key>``-style pairs
        (e.g., Qwen3-Coder's ``<parameter=KEY>VALUE</parameter>``). Set ``key_prefix``,
        ``key_suffix``, and ``value_end``; each extracted value is tried as JSON and
        falls back to its stripped raw string.

    Exactly one shape must be set — mixing wrapper and repeat fields is rejected.
    """
    prefix: Optional[str] = Field(default=None, description="Wrapper shape: literal string that opens the arguments payload (e.g., '```json\\n').")
    suffix: Optional[str] = Field(default=None, description="Wrapper shape: literal string that closes the arguments payload (e.g., '\\n```').")
    key_prefix: Optional[str] = Field(default=None, description="Repeat shape: literal string immediately before each parameter key (e.g., '<parameter=').")
    key_suffix: Optional[str] = Field(default=None, description="Repeat shape: literal string immediately after each parameter key (e.g., '>').")
    value_end: Optional[str] = Field(default=None, description="Repeat shape: literal string that closes each parameter value (e.g., '</parameter>').")

    @model_validator(mode="after")
    def validate_shape(self):
        wrapper_fields = [ ("prefix", self.prefix), ("suffix", self.suffix) ]
        repeat_fields  = [ ("key_prefix", self.key_prefix), ("key_suffix", self.key_suffix), ("value_end", self.value_end) ]
        wrapper_keys   = [ key for key, value in wrapper_fields if value is not None ]
        repeat_keys    = [ key for key, value in repeat_fields if value is not None ]
        if wrapper_keys and repeat_keys:
            raise ValueError("arguments_marker mixes wrapper fields (prefix/suffix) with repeat fields (key_prefix/key_suffix/value_end); use one shape or the other.")
        if wrapper_keys and len(wrapper_keys) < 2:
            raise ValueError("arguments_marker wrapper shape requires both 'prefix' and 'suffix'.")
        if repeat_keys and len(repeat_keys) < 3:
            raise ValueError("arguments_marker repeat shape requires 'key_prefix', 'key_suffix', and 'value_end'.")
        if not wrapper_keys and not repeat_keys:
            raise ValueError("arguments_marker requires either the wrapper shape (prefix/suffix) or the repeat shape (key_prefix/key_suffix/value_end).")
        return self

    @property
    def is_repeat_shape(self) -> bool:
        return self.key_prefix is not None

class ToolCallParserConfig(BaseModel):
    batch_start_tag: Optional[str] = Field(default=None, description="Optional outer marker that opens a batch of tool calls (e.g., DeepSeek's '<｜tool_calls_begin｜>').")
    batch_end_tag: Optional[str] = Field(default=None, description="Optional outer marker that closes a batch of tool calls.")
    start_tag: str = Field(..., description="Literal marker that opens a single tool call in the model output (e.g., '<tool_call>').")
    end_tag: Optional[str] = Field(default=None, description="Literal marker that closes a single tool call; omit to parse one JSON/pythonic value immediately following the start marker.")
    format: ToolCallBodyFormat = Field(default=ToolCallBodyFormat.JSON, description="Body syntax between the markers (json, pythonic, or xml).")
    name_key: str = Field(default="name", description="JSON field name that holds the tool name. Ignored when name_marker is set.")
    arguments_key: str = Field(default="arguments", description="JSON field name that holds the tool arguments. Ignored when arguments_marker is set.")
    name_marker: Optional[ToolCallNameMarker] = Field(default=None, description="Locate the tool name as a literal between two markers in the body instead of reading a JSON field.")
    arguments_marker: Optional[ToolCallArgumentsMarker] = Field(default=None, description="Locate the arguments inside a wrapper (prefix/suffix) or as repeating key/value pairs (key_prefix/key_suffix/value_end).")

    @model_validator(mode="after")
    def validate_keys_for_non_json_format(self):
        if self.format != ToolCallBodyFormat.JSON and (self.name_key != "name" or self.arguments_key != "arguments"):
            raise ValueError(f"name_key and arguments_key have no effect when format is '{self.format.value}'.")
        return self

    @model_validator(mode="after")
    def validate_markers_for_format(self):
        if self.format == ToolCallBodyFormat.PYTHONIC and (self.name_marker is not None or self.arguments_marker is not None):
            raise ValueError("name_marker and arguments_marker are not supported when format is 'pythonic'.")
        if self.format == ToolCallBodyFormat.JSON and self.arguments_marker is not None and self.arguments_marker.is_repeat_shape:
            raise ValueError("arguments_marker repeat shape (key_prefix/key_suffix/value_end) is only supported when format is 'xml'.")
        if self.format == ToolCallBodyFormat.XML:
            if self.name_marker is None:
                raise ValueError("name_marker is required when format is 'xml'.")
            if self.arguments_marker is None or not self.arguments_marker.is_repeat_shape:
                raise ValueError("arguments_marker with the repeat shape (key_prefix/key_suffix/value_end) is required when format is 'xml'.")
        return self

    @model_validator(mode="after")
    def validate_end_tag_for_xml_format(self):
        if self.format == ToolCallBodyFormat.XML and self.end_tag is None:
            raise ValueError("end_tag is required when format is 'xml'; XML bodies have no self-delimiting syntax.")
        return self

    @model_validator(mode="after")
    def validate_batch_tags_paired(self):
        if (self.batch_start_tag is None) != (self.batch_end_tag is None):
            raise ValueError("batch_start_tag and batch_end_tag must be set together.")
        return self

class ReasoningParserConfig(BaseModel):
    start_tag: Optional[str] = Field(default=None, description="Literal marker that opens a reasoning span (e.g. '<think>'). Omit for models that begin reasoning at the start of the output (e.g. Qwen3 thinking mode) — everything up to end_tag is treated as reasoning.")
    end_tag: str = Field(..., description="Literal marker that closes a reasoning span (e.g. '</think>').")

class CommonChatCompletionModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.CHAT_COMPLETION]
    chat_template: Optional[str] = Field(default=None, description="Inline Jinja chat template string, overriding the tokenizer default.")
    tools: Optional[List[ModelTool]] = Field(default=None, description="Catalog of tools this component exposes for tool calling.")
    reasoning_parser: Optional[ReasoningParserConfig] = Field(default=None, description="Rules for extracting reasoning spans (e.g. '<think>...</think>') from raw model output. Applied before tool_call_parser.")
    tool_call_parser: Optional[ToolCallParserConfig] = Field(default=None, description="Rules for extracting tool calls from raw model output.")
