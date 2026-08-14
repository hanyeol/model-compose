from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import field_validator

class CommonActionConfig(BaseModel):
    id: str = Field(default="__action__", description="ID of action.")
    output: Optional[Any] = Field(default=None, description="Output mapping that transforms and extracts values from the action's result.")
    default: bool = Field(default=False, description="Whether to use this action when none is explicitly selected.")

    @field_validator("id")
    def validate_id(cls, value):
        if value == "__default__":
            raise ValueError("Action id cannot be '__default__'")
        return value
