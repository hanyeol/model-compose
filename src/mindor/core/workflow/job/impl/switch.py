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

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input = (await context.render_variable(None, self.config.input)) if self.config.input else context.workflow.input

        await self._started(input)

        input = await self._before_run(context, None, input)

        target = self.config.otherwise
        for case in self.config.cases:
            value = await context.render_variable(None, case.value)
            if input == value:
                target = case.then
                break

        await self._after_run(context, None, input, None)

        return RoutingTarget(target)
