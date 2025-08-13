from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import CommonActionConfig
from .types import JobType

class CommonJobConfig(BaseModel):
    id: str = Field(default="__default__", description="ID of job.")
    type: JobType = Field(..., description="Type of job.")
    depends_on: List[str] = Field(default_factory=list, description="Jobs that must complete before this job runs.")

    def get_routing_jobs(self) -> List[str]:
        return []

class OutputJobConfig(CommonJobConfig):
    output: Optional[Any] = Field(default=None, description="The output data returned from this job. Accepts any type.")
