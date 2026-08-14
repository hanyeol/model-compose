from __future__ import annotations

from typing import Optional, Dict, List, Literal, Any
from pydantic import BaseModel, Field, model_validator

class ModelToolProperty(BaseModel):
    type: Literal[ "string", "integer", "number", "boolean", "array", "object" ] = Field(..., description="JSON Schema type of this parameter.")
    description: Optional[str] = Field(default=None, description="Human-readable explanation of what this parameter is for.")
    enum: Optional[List[Any]] = Field(default=None, description="Allowed values this parameter may take.")
    items: Optional[ModelToolProperty] = Field(default=None, description="Schema of array elements when `type` is 'array'.")
    properties: Optional[Dict[str, ModelToolProperty]] = Field(default=None, description="Schemas of nested properties when `type` is 'object'.")
    format: Optional[str] = Field(default=None, description="Semantic format hint for the parameter value (e.g., 'date-time', 'email', 'uri').")
    default: Optional[Any] = Field(default=None, description="Value used when the parameter is omitted.")
    required: Optional[List[str]] = Field(default=None, description="Names of nested properties that must be provided when `type` is 'object'.")

    model_config = { "extra": "allow" }

    @model_validator(mode="after")
    def _validate_type_specific_fields(self):
        if self.items is not None and self.type != "array":
            raise ValueError(f"'items' is only valid when type is 'array' (got type='{self.type}').")
        if self.properties is not None and self.type != "object":
            raise ValueError(f"'properties' is only valid when type is 'object' (got type='{self.type}').")
        if self.required is not None and self.type != "object":
            raise ValueError(f"'required' is only valid when type is 'object' (got type='{self.type}').")
        if self.enum is not None and self.type not in ("string", "integer", "number"):
            raise ValueError(f"'enum' is only valid when type is 'string', 'integer', or 'number' (got type='{self.type}').")
        return self

class ModelToolParameters(BaseModel):
    type: Literal[ "object" ] = Field(default="object", description="JSON Schema container type; always 'object'.")
    properties: Dict[str, ModelToolProperty] = Field(default_factory=dict, description="Parameter schemas keyed by parameter name.")
    required: List[str] = Field(default_factory=list, description="Names of parameters that must be provided when invoking the tool.")

class ModelTool(BaseModel):
    name: str = Field(..., description="Name of tool.")
    description: Optional[str] = Field(default=None, description="Human-readable explanation of what the tool does.")
    parameters: Optional[ModelToolParameters] = Field(default=None, description="Schema of parameters the tool accepts.")
