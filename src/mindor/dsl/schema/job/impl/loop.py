from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from .common import JobType, CompositeJobConfig

class LoopJobConditionConfig(BaseModel):
    input: Optional[Any] = Field(default=None, description="Value evaluated each iteration, typically `${output.*}`; required on leaf predicates.")
    operator: ConditionOperator = Field(default=ConditionOperator.EQ, description="Operator used to compare `input` against `value` in a leaf predicate.")
    value: Optional[Any] = Field(default=None, description="Value the input is compared against in a leaf predicate.")
    all: Optional[List[LoopJobConditionConfig]] = Field(default=None, description="Logical AND combinator; every nested predicate must match.")
    any: Optional[List[LoopJobConditionConfig]] = Field(default=None, description="Logical OR combinator; at least one nested predicate must match.")
    not_: Optional[LoopJobConditionConfig] = Field(default=None, alias="not", description="Logical NOT combinator; inverts the nested predicate.")

    model_config = { "populate_by_name": True }

    @model_validator(mode="after")
    def validate_predicates(self):
        combinators = [ key for key, value in [ ("all", self.all), ("any", self.any), ("not", self.not_) ] if value is not None ]
        is_leaf_condition = self.input is not None or self.value is not None

        if len(combinators) > 1:
            raise ValueError(f"Loop condition may use at most one of `all`, `any`, `not`; got {combinators}.")
        if combinators and is_leaf_condition:
            raise ValueError(f"Loop condition mixes leaf predicate (`input`/`value`) with combinator `{combinators[0]}`; use one or the other.")
        if not combinators and not is_leaf_condition:
            raise ValueError("Loop condition requires either a leaf predicate (`input`/`value`) or one of `all`/`any`/`not`.")

        return self

class LoopJobConfig(CompositeJobConfig):
    type: Literal[JobType.LOOP]
    input: Optional[Any] = Field(default=None, description="Initial value passed to the first iteration.")
    do: "InlineJobConfig" = Field(..., description="Job executed each iteration; its output becomes next iteration's input.")
    while_: Optional[LoopJobConditionConfig] = Field(default=None, alias="while", description="Predicate evaluated after each iteration; loop continues while it matches.")
    until: Optional[LoopJobConditionConfig] = Field(default=None, description="Predicate evaluated after each iteration; loop stops when it matches.")
    max_iteration_count: int = Field(default=100, gt=0, description="Safety cap on iterations regardless of the condition.")

    model_config = { "populate_by_name": True }

    @field_validator("do", mode="before")
    def inflate_default_do_type(cls, value):
        if isinstance(value, dict) and "type" not in value:
            value["type"] = JobType.COMPONENT.value
        return value

    @model_validator(mode="after")
    def validate_condition(self):
        if (self.while_ is None) == (self.until is None):
            raise ValueError("Exactly one of 'while' or 'until' must be set.")
        return self

    @model_validator(mode="after")
    def validate_inline_job(self):
        if getattr(self.do, "depends_on", None):
            raise ValueError("Inline `do` job cannot declare 'depends_on'.")
        return self

    def get_scope_isolated_fields(self) -> Set[str]:
        # `do`'s `${input}`/`${output}` refer to the loop's own scope, not the surrounding workflow scope.
        return { "do" }
