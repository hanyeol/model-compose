from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import McpClientActionConfig
from .common import ComponentType, CommonComponentConfig

class McpClientComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MCP_CLIENT]
    url: str = Field(..., description="URL of the MCP server to invoke tools.")
    headers: Dict[str, Any] = Field(default_factory=dict, description="HTTP headers to include when connecting to the MCP server.")
    actions: List[McpClientActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(McpClientActionConfig.model_fields.keys()) - set(CommonComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
