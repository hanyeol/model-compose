from typing import Optional
from pydantic import BaseModel, Field
from .types import SystemType

class CommonSystemConfig(BaseModel):
    id: str = Field(default="__system__", description="Unique system identifier.")
    type: SystemType = Field(..., description="System type.")
