from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .common import JobType, CommonJobConfig

class IfConditionOperator(str, Enum):
    EQ          = "eq"
    NEQ         = "neq"
    GT          = "gt"
    GTE         = "gte"
    LT          = "lt"
    LTE         = "lte"
    IN          = "in"
    NOT_IN      = "not-in"
    STARTS_WITH = "starts-with"
    ENDS_WITH   = "ends-with"
    MATCH       = "match"

class IfConditionConfig(BaseModel):
    operator: IfConditionOperator = Field(default=IfConditionOperator.EQ, description="Condition operator.")
    input: Optional[Any] = Field(default=None, description="Input to evaluate.")
    value: Optional[Any] = Field(default=None, description="Value to compare against.")
    if_true: Optional[str] = Field(default=None, description="Job ID to run if condition is true.")
    if_false: Optional[str] = Field(default=None, description="Job ID to run if condition is false.")

class IfJobConfig(CommonJobConfig):
    type: Literal[JobType.IF]
    conditions: List[IfConditionConfig] = Field(default_factory=list, description="List of conditions to evaluate.")
    otherwise: Optional[str] = Field(default=None, description="Job ID to run if no conditions matched or no result returned.")

    @model_validator(mode="before")
    def inflate_single_condition(cls, values: Dict[str, Any]):
        if "conditions" not in values:
            condition_keys = set(IfConditionConfig.model_fields.keys()) - set(CommonJobConfig.model_fields.keys())
            if any(k in values for k in condition_keys):
                values["conditions"] = [ { k: values.pop(k) for k in condition_keys if k in values } ]
        return values

    def get_routing_jobs(self) -> Set[str]:
        jobs: Set[str] = set()
        for condition in self.conditions:
            jobs.update(job_id for job_id in (condition.if_true, condition.if_false) if job_id)
        if self.otherwise:
            jobs.add(self.otherwise)
        return jobs
