from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import ComponentJobConfig, JobType
from mindor.core.component import ComponentService, ComponentGlobalConfigs
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import JobType, JobContext, RoutingTarget, register_job
from .common import ComponentRunnerJob
from datetime import datetime
import asyncio, ulid

@register_job(JobType.COMPONENT)
class ComponentJob(ComponentRunnerJob):
    def __init__(self, id: str, config: ComponentJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        component: ComponentService = await self._create_component(self.id, self.config.component)

        input        = (await context.render_variable(None, self.config.input)) if self.config.input else context.workflow.input
        repeat_count = (await context.render_variable(None, self.config.repeat_count)) if self.config.repeat_count else None

        await self._started(input)

        outputs = await asyncio.gather(*[ self._run_once(input, component, context) for _ in range(int(repeat_count or 1)) ])

        output = outputs[0] if len(outputs) == 1 else outputs or None
        context.register_source(None, "output", output)

        return output

    async def _run_once(self, input: Any, component: ComponentService, context: JobContext) -> Any:
        run_id: str = ulid.ulid()
        context.workflow.record_run_id(self.id, run_id)

        job_time_tracker = TimeTracker()
        logging.debug("[task-%s] Run '%s:%s' for job '%s:%s' started.", context.workflow.task_id, run_id, component.id, self.id, context.workflow.workflow_id)

        is_direct_output = not self.config.output or self.config.output == "${output}"

        input = await self._before_run(context, run_id, input)

        output = await component.run(self.config.action, run_id, input, workflow=context.workflow, job_id=self.id)
        output = await self._after_run(context, run_id, input, output)

        if not is_direct_output:
            context.register_source(run_id, "output", output)
            output = await context.render_variable(run_id, self.config.output, skip_decode=context.is_terminal)

        logging.debug("[task-%s] Run '%s:%s' for job '%s:%s' completed in %.2f seconds.", context.workflow.task_id, run_id, component.id, self.id, context.workflow.workflow_id, job_time_tracker.elapsed())

        return output
