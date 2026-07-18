from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import IfJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.evaluator.condition import evaluate_condition
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
import asyncio

@register_job(JobType.IF)
class IfJob(Job):
    def __init__(self, id: str, config: IfJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input = await context.render_variable(None, self.config.input)

        input = await self._before_run(context, None, input)

        target: Optional[str] = None
        for condition in self.config.conditions:
            value = await context.render_variable(None, condition.value)

            logging.debug("[task-%s] Evaluating condition: %s %s %s", context.workflow.task_id, input, condition.operator, value)

            if evaluate_condition(condition.operator, input, value):
                if condition.if_true:
                    target = condition.if_true
                    break
            else:
                if condition.if_false:
                    target = condition.if_false
                    break

        if target is None:
            target = await context.render_variable(None, self.config.otherwise)

        await self._after_run(context, None, input, None)

        return RoutingTarget(target)
