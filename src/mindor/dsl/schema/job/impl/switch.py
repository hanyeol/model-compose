from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .common import JobType, CommonJobConfig

class SwitchCaseConfig(BaseModel):
    value: Optional[Any] = Field(default=None, description="")
    then: Optional[str] = Field(default=None, description="")

class SwitchJobConfig(CommonJobConfig):
    type: Literal[JobType.SWITCH]
    input: Optional[Any] = Field(default=None, description="")
    cases: List[SwitchCaseConfig] = Field(default_factory=list, description="")
    otherwise: Optional[str] = Field(default=None, description="")

    @classmethod
    def inflate_single_case(cls, values: Dict[str, Any]):
        if "cases" not in values:
            case_keys = set(SwitchCaseConfig.model_fields.keys())
            if any(k in values for k in case_keys):
                values["cases"] = [ { k: values.pop(k) for k in case_keys if k in values } ]
        return values
