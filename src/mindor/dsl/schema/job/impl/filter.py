from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from .common import JobType, OutputJobConfig

class FilterJobConditionConfig(BaseModel):
    input: Optional[Any] = Field(default=None, description="Value evaluated for the current item, typically `${item.*}`; required on leaf predicates.")
    operator: ConditionOperator = Field(default=ConditionOperator.EQ, description="Operator used to compare `input` against `value` in a leaf predicate.")
    value: Optional[Any] = Field(default=None, description="Value the input is compared against in a leaf predicate.")
    all: Optional[List[FilterJobConditionConfig]] = Field(default=None, description="Logical AND combinator; every nested predicate must match.")
    any: Optional[List[FilterJobConditionConfig]] = Field(default=None, description="Logical OR combinator; at least one nested predicate must match.")
    not_: Optional[FilterJobConditionConfig] = Field(default=None, alias="not", description="Logical NOT combinator; inverts the nested predicate.")

    @model_validator(mode="after")
    def validate_predicates(self):
        combinators = [ key for key, value in [ ("all", self.all), ("any", self.any), ("not", self.not_) ] if value is not None ]
        is_leaf_condition = self.input is not None or self.value is not None

        if len(combinators) > 1:
            raise ValueError(f"Filter condition may use at most one of `all`, `any`, `not`; got {combinators}.")
        if combinators and is_leaf_condition:
            raise ValueError(f"Filter condition mixes leaf predicate (`input`/`value`) with combinator `{combinators[0]}`; use one or the other.")
        if not combinators and not is_leaf_condition:
            raise ValueError("Filter condition requires either a leaf predicate (`input`/`value`) or one of `all`/`any`/`not`.")

        return self

class FilterJobConfig(OutputJobConfig):
    type: Literal[JobType.FILTER]
    input: Any = Field(..., description="Source list or async stream of items to filter.")
    where: Optional[FilterJobConditionConfig] = Field(default=None, description="Predicate evaluated per item; every item is kept when omitted.")
    streaming: bool = Field(default=False, description="Whether surviving items are yielded incrementally as they arrive.")
