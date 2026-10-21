from typing import Optional, Any
from pydantic import BaseModel, Field

class ComponentRunConfig(BaseModel):
    component: str = Field(..., description="ID of the component to run.")
    action: str = Field(default="__default__", description="ID of the action to run on the component.")
    input: Optional[Any] = Field(default=None, description="Input mapping passed to the component.")
    output: Optional[Any] = Field(default=None, description="Output mapping that transforms the component's response.")
