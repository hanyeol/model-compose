from __future__ import annotations

from typing import Optional, Dict, List, Literal, Any
from pydantic import BaseModel, Field, model_validator

class ModelToolProperty(BaseModel):
    type: Literal[ "string", "integer", "number", "boolean", "array", "object" ] = Field(..., description="Parameter type.")
    description: Optional[str] = Field(default=None, description="What this parameter is for.")
    enum: Optional[List[Any]] = Field(default=None, description="Allowed values for this parameter.")
    items: Optional[ModelToolProperty] = Field(default=None, description="Item schema when type is 'array'.")
    properties: Optional[Dict[str, ModelToolProperty]] = Field(default=None, description="Nested parameter schemas when type is 'object'.")
    format: Optional[str] = Field(default=None, description="Semantic format hint (e.g., 'date-time', 'email', 'uri').")
    default: Optional[Any] = Field(default=None, description="Default value used when the parameter is omitted.")
    required: Optional[List[str]] = Field(default=None, description="Names of required nested parameters when type is 'object'.")

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
    type: Literal[ "object" ] = Field(default="object", description="Schema container type. Always 'object'.")
    properties: Dict[str, ModelToolProperty] = Field(default_factory=dict, description="Parameter schemas keyed by parameter name.")
    required: List[str] = Field(default_factory=list, description="Names of parameters that must be provided.")

class ModelTool(BaseModel):
    name: str = Field(..., description="Tool name.")
    description: Optional[str] = Field(default=None, description="Tool description.")
    parameters: Optional[ModelToolParameters] = Field(default=None, description="Parameters that the tool accepts.")
