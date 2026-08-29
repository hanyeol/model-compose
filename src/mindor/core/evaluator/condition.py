from typing import Any, Awaitable, Callable, Dict
from mindor.dsl.schema.common.operator.condition import ConditionOperator
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

    if operator == ConditionOperator.STARTS_WITH:
        return input.startswith(value)

    if operator == ConditionOperator.ENDS_WITH:
        return input.endswith(value)

    if operator == ConditionOperator.MATCH:
        return bool(re.match(value, input))

    raise ValueError(f"Unsupported operator: {operator}")

async def evaluate_where(where: Dict[str, Any], evaluator: Callable[[Dict[str, Any]], Awaitable[bool]]) -> bool:
    all_conditions = where.get("all")
    if all_conditions is not None:
        for condition in all_conditions:
            if not await evaluate_where(condition, evaluator):
                return False
        return True

    any_conditions = where.get("any")
    if any_conditions is not None:
        for condition in any_conditions:
            if await evaluate_where(condition, evaluator):
                return True
        return False

    not_condition = where.get("not")
    if not_condition is not None:
        return not await evaluate_where(not_condition, evaluator)

    return await evaluator(where)
