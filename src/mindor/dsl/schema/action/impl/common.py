from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import field_validator

class CommonActionConfig(BaseModel):
    id: str = Field(default="__action__", description="ID of action.")
    output: Optional[Any] = Field(default=None, description="Output mapping to transform and extract specific values from the action result.")
    default: bool = Field(default=False, description="Whether this action should be used as the default.")

    @field_validator("id")
    def validate_id(cls, value):
        if value == "__default__":
            raise ValueError("Action id cannot be '__default__'")
        return value
