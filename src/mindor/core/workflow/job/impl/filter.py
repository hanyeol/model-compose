from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import FilterJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.evaluator.condition import evaluate_condition
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job

@register_job(JobType.FILTER)
class FilterJob(Job):
    config: FilterJobConfig

    def __init__(self, id: str, config: FilterJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input = await context.render_variable(None, self.config.input)

        if not isinstance(input, list):
            raise TypeError(f"filter job '{self.id}' expects a list input, got {type(input).__name__}")

        if self.config.where is not None:
            output: List[Any] = [ item for item in input if await self._matches(context, item) ]
        else:
            output = list(input)

        context.register_source(None, "output", output)

        return (await context.render_variable(None, self.config.output)) if self.config.output else output

    async def _matches(self, context: JobContext, item: Any) -> bool:
        context.register_source(self.id, "item", item)

        input = await context.render_variable(self.id, self.config.where.input)
        value = await context.render_variable(self.id, self.config.where.value)

        return evaluate_condition(self.config.where.operator, input, value)
