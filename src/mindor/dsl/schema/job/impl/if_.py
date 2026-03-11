from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.operator.condition import ConditionOperator
from .common import JobType, CommonJobConfig

class IfJobConditionConfig(BaseModel):
    operator: ConditionOperator = Field(default=ConditionOperator.EQ, description="Condition operator.")
    input: Optional[Any] = Field(default=None, description="Input to evaluate.")
    value: Optional[Any] = Field(default=None, description="Value to compare against.")
    if_true: Optional[str] = Field(default=None, description="Job ID to run if condition is true.")
    if_false: Optional[str] = Field(default=None, description="Job ID to run if condition is false.")

class IfJobConfig(CommonJobConfig):
    type: Literal[JobType.IF]
    conditions: List[IfJobConditionConfig] = Field(default_factory=list, description="List of conditions to evaluate.")
    otherwise: Optional[str] = Field(default=None, description="Job ID to run if no conditions matched or no result returned.")

    @model_validator(mode="before")
    def inflate_single_condition(cls, values: Dict[str, Any]):
        if "conditions" not in values:
            condition_keys = set(IfJobConditionConfig.model_fields.keys()) - set(CommonJobConfig.model_fields.keys())
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
