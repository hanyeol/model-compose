from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from .common import JobType, CommonJobConfig

class IfJobConditionConfig(BaseModel):
    operator: ConditionOperator = Field(default=ConditionOperator.EQ, description="Operator used to compare `input` against `value`.")
    value: Optional[Any] = Field(default=None, description="Value the input is compared against.")
    if_true: Optional[str] = Field(default=None, description="ID of the job to route to when the condition matches.")
    if_false: Optional[str] = Field(default=None, description="ID of the job to route to when the condition does not match.")

class IfJobConfig(CommonJobConfig):
    type: Literal[JobType.IF]
    input: Optional[Any] = Field(default=None, description="Value evaluated against each condition.")
    conditions: List[IfJobConditionConfig] = Field(default_factory=list, description="Conditions evaluated in order to decide routing.")
    otherwise: Optional[str] = Field(default=None, description="ID of the job to route to when no condition matches.")

    @model_validator(mode="before")
    def inflate_single_condition(cls, values: Dict[str, Any]):
        if "conditions" not in values:
            condition_keys = set(IfJobConditionConfig.model_fields.keys()) - set(CommonJobConfig.model_fields.keys())
            if any(k in values for k in condition_keys):
                values["conditions"] = [ { k: values.pop(k) for k in condition_keys if k in values } ]
        return values

    def get_routing_jobs(self) -> Set[str]:
        jobs = super().get_routing_jobs()
        for condition in self.conditions:
            jobs.update(job_id for job_id in (condition.if_true, condition.if_false) if job_id)
        if self.otherwise:
            jobs.add(self.otherwise)
        return jobs
