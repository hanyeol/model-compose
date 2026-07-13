from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from .common import JobType, OutputJobConfig

class FilterJobConditionConfig(BaseModel):
    input: Any = Field(..., description="Value to evaluate for the current item, typically references `${item.*}`.")
    operator: ConditionOperator = Field(default=ConditionOperator.EQ, description="Condition operator.")
    value: Optional[Any] = Field(default=None, description="Value to compare against.")

class FilterJobConfig(OutputJobConfig):
    type: Literal[JobType.FILTER]
    input: Any = Field(..., description="Source list or async stream to filter. Each element is exposed as `${item}` and its position as `${index}` while rendering `where` and `output`.")
    where: Optional[FilterJobConditionConfig] = Field(default=None, description="Predicate evaluated per item. If omitted, every item is kept.")
    streaming: bool = Field(default=False, description="If true, yield surviving items as they arrive instead of materializing the full list. Automatically enabled when `input` is a stream.")
