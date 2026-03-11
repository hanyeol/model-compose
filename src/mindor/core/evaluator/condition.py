from typing import Any
from mindor.dsl.schema.operator.condition import ConditionOperator
import re

def evaluate_condition(operator: ConditionOperator, input: Any, value: Any) -> bool:
    if operator == ConditionOperator.EQ:
        return input == value

    if operator == ConditionOperator.NEQ:
        return input != value

    if operator == ConditionOperator.GT:
        return input > value

    if operator == ConditionOperator.GTE:
        return input >= value

    if operator == ConditionOperator.LT:
        return input < value

    if operator == ConditionOperator.LTE:
        return input <= value

    if operator == ConditionOperator.IN:
        return input in value

    if operator == ConditionOperator.NOT_IN:
        return input not in value

    if operator == ConditionOperator.MATCH:
        return bool(re.match(value, input))

    raise ValueError(f"Unsupported operator: {operator}")
