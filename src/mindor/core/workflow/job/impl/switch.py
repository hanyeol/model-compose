from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import SwitchJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
import asyncio

@register_job(JobType.SWITCH)
class SwitchJob(Job):
    def __init__(self, id: str, config: SwitchJobConfig, global_configs: ComponentGlobalConfigs):
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

        target = self.config.otherwise
        for case in self.config.cases:
            value = await context.render_variable(run_id, case.value)
            if input == value:
                target = case.then
                break

        await self._after_run(context, run_id, input, None)

        return RoutingTarget(target)
