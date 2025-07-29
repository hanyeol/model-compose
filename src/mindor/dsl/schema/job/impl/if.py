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
    operator: IfConditionOperator = Field(default=IfConditionOperator.EQ, description="")
    input: Optional[Any] = Field(default=None, description="")
    value: Optional[Any] = Field(default=None, description="")
    if_true: Optional[str] = Field(default=None, description="")
    if_false: Optional[str] = Field(default=None, description="")

class IfJobConfig(CommonJobConfig):
    type: Literal[JobType.IF]
    conditions: List[IfConditionConfig] = Field(default_factory=list, description="")

    @classmethod
    def inflate_single_condition(cls, values: Dict[str, Any]):
        if "conditions" not in values:
            condition_keys = set(IfConditionConfig.model_fields.keys())
            if any(k in values for k in condition_keys):
                values["conditions"] = [ { k: values.pop(k) for k in condition_keys if k in values } ]
        return values
