from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .common import JobType, CommonJobConfig

class SwitchCaseConfig(BaseModel):
    value: str = Field(..., description="Value to match against the input.")
    then: str = Field(..., description="Job ID to route to if the value matches.")

class SwitchJobConfig(CommonJobConfig):
    type: Literal[JobType.SWITCH]
    input: Optional[Any] = Field(default=None, description="Value to match against switch cases.")
    cases: List[SwitchCaseConfig] = Field(default_factory=list, description="List of cases to evaluate.")
    otherwise: Optional[str] = Field(default=None, description="Job ID to route to if no cases match.")

    @model_validator(mode="before")
    def inflate_single_case(cls, values: Dict[str, Any]):
        if "cases" not in values:
            case_keys = set(SwitchCaseConfig.model_fields.keys()) - set(CommonJobConfig.model_fields.keys())
            if any(k in values for k in case_keys):
                values["cases"] = [ { k: values.pop(k) for k in case_keys if k in values } ]
        return values

    def get_routing_jobs(self) -> Set[str]:
        jobs = { case.then for case in self.cases }
        if self.otherwise:
            jobs.add(self.otherwise)
        return jobs
