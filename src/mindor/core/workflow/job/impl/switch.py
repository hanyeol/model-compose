from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import SwitchJobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.logger import logging
from ..base import Job, JobType, WorkflowContext, RoutingTarget, register_job
import asyncio

@register_job(JobType.SWITCH)
class SwitchJob(Job):
    def __init__(self, id: str, config: SwitchJobConfig, components: Dict[str, ComponentConfig]):
        super().__init__(id, config, components)

    async def run(self, context: WorkflowContext) -> Union[Any, RoutingTarget]:
        input = (await context.render_variable(self.config.input)) if self.config.input else context.input

        for case in self.config.cases:
            value = await context.render_variable(case.value)
            if input == value:
                return RoutingTarget(case.then)

        return RoutingTarget(self.config.otherwise)
