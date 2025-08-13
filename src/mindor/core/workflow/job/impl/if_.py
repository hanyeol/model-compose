from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import IfJobConfig, IfConditionOperator
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.logger import logging
from ..base import Job, JobType, WorkflowContext, RoutingTarget, register_job
import asyncio, re

@register_job(JobType.IF)
class IfJob(Job):
    def __init__(self, id: str, config: IfJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def run(self, context: WorkflowContext) -> Union[Any, RoutingTarget]:
        for condition in self.config.conditions:
            input = await context.render_variable(condition.input)
            value = await context.render_variable(condition.value)

            logging.debug("[task-%s] Evaluating condition: %s %s %s", context.task_id, input, condition.operator, value)

            if self._evaluate_condition(condition.operator, input, value):
                if condition.if_true:
                    return RoutingTarget(condition.if_true)
            else:
                if condition.if_false:
                    return RoutingTarget(condition.if_false)

        return RoutingTarget(await context.render_variable(self.config.otherwise))

    def _evaluate_condition(self, operator: IfConditionOperator, input: Any, value: Any) -> bool:
        if operator == IfConditionOperator.EQ:
            return input == value

        if operator == IfConditionOperator.NEQ:
            return input != value
        
        if operator == IfConditionOperator.GT:
            return input > value
        
        if operator == IfConditionOperator.GTE:
            return input >= value
        
        if operator == IfConditionOperator.LT:
            return input < value
        
        if operator == IfConditionOperator.LTE:
            return input <= value
        
        if operator == IfConditionOperator.IN:
            return input in value
        
        if operator == IfConditionOperator.NOT_IN:
            return input not in value
        
        if operator == IfConditionOperator.MATCH:
            return bool(re.match(value, input))

        raise ValueError(f"Unsupported operator: {operator}")
