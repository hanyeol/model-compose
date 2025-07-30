from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import ActionJobConfig, JobType
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs, ComponentResolver, create_component
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import Job, JobType, WorkflowContext, RoutingTarget, register_job
from datetime import datetime
import asyncio, ulid

@register_job(JobType.ACTION)
class ActionJob(Job):
    def __init__(self, id: str, config: ActionJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def run(self, context: WorkflowContext) -> Union[Any, RoutingTarget]:
        component: ComponentService = self._create_component(self.id, await context.render_variable(self.config.component))

        if not component.started:
            await component.start()

        input = (await context.render_variable(self.config.input)) if self.config.input else context.input
        outputs = []

        async def _run_once():
            run_id: str = ulid.ulid()

            job_time_tracker = TimeTracker()
            logging.debug("[task-%s] Action 'run-%s' started for job '%s'", context.task_id, run_id, self.id)

            output = await component.run(await context.render_variable(self.config.action), run_id, input)
            context.register_source("output", output)

            logging.debug("[task-%s] Action 'run-%s' completed in %.2f seconds.", context.task_id, run_id, job_time_tracker.elapsed())

            output = (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else output
            outputs.append(output)

        repeat_count = (await context.render_variable(self.config.repeat_count)) if self.config.repeat_count else None
        await asyncio.gather(*[ _run_once() for _ in range(int(repeat_count or 1)) ])

        output = outputs[0] if len(outputs) == 1 else outputs or None
        context.register_source("output", output)

        return output

    def _create_component(self, id: str, component: Union[ComponentConfig, str]) -> ComponentService:
        return create_component(*self._resolve_component(id, component), self.global_configs, daemon=False)

    def _resolve_component(self, id: str, component: Union[ComponentConfig, str]) -> Tuple[str, ComponentConfig]:
        if isinstance(component, str):
            return ComponentResolver(self.global_configs.components).resolve(component)
    
        return id, component
