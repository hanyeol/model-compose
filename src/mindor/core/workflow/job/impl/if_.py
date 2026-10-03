from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import IfJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.foundation.condition import evaluate_condition
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
import asyncio

@register_job(JobType.IF)
class IfJob(Job):
    def __init__(self, id: str, config: IfJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(
        self,
        context: JobContext,
        run_id: Optional[str],
        default_input: Any,
        is_terminal: bool,
    ) -> Union[Any, RoutingTarget]:
        input = await context.render_variable(run_id, self.config.input) if self.config.input is not None else self._default_input(context, default_input)

        await self._started(input)

        input = await self._before_run(context, run_id, input)

        target: Optional[str] = None

        for condition in self.config.conditions:
            value = await context.render_variable(run_id, condition.value)

            logging.debug(
                "[task-%s] Evaluating condition: %s %s %s",
                context.workflow.task_id,
                input,
                condition.operator,
                value,
            )

            if evaluate_condition(condition.operator, input, value):
                if condition.if_true:
                    target = condition.if_true
                    break
            else:
                if condition.if_false:
                    target = condition.if_false
                    break

        if target is None:
            target = await context.render_variable(run_id, self.config.otherwise)

        await self._after_run(context, run_id, input, None)

        return RoutingTarget(target)
