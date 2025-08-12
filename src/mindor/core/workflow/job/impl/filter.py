from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import FilterJobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.logger import logging
from ..base import Job, JobType, WorkflowContext, RoutingTarget, register_job

@register_job(JobType.FILTER)
class FilterJob(Job):
    def __init__(self, id: str, config: FilterJobConfig, components: Dict[str, ComponentConfig]):
        super().__init__(id, config, components)

    async def run(self, context: WorkflowContext) -> Union[Any, RoutingTarget]:
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else None
