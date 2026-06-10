from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.job import ComponentJobConfig, ComponentInterruptPointConfig, JobType
from mindor.core.evaluator.condition import evaluate_condition
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs, ComponentResolver, create_component
from mindor.core.workflow.interrupt import InterruptPoint
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
from datetime import datetime
import asyncio, ulid

@register_job(JobType.COMPONENT)
class ComponentJob(Job):
    def __init__(self, id: str, config: ComponentJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        component: ComponentService = self._create_component(self.id, self.config.component)

        if not component.started:
            await component.start()

        input = (await context.render_variable(None, self.config.input)) if self.config.input else context.workflow.input
        outputs = []

        async def _run_once(input: Any):
            run_id: str = ulid.ulid()
            context.workflow.record_run_id(self.id, run_id)

            job_time_tracker = TimeTracker()
            logging.debug("[task-%s] Run '%s:%s' for job '%s:%s' started.", context.workflow.task_id, run_id, component.id, self.id, context.workflow.workflow_id)

            if self.config.interrupt and self.config.interrupt.before:
                logging.info("[task-%s] Job '%s:%s' interrupted at 'before' phase.", context.workflow.task_id, self.id, context.workflow.workflow_id)
                context.register_source(run_id, "job", { "input": input })
                answer = await self._interrupt(context, run_id, "before", self.config.interrupt.before)
                if answer is not None:
                    input = answer

            output = await component.run(self.config.action, run_id, input, workflow=context.workflow, job_id=self.id)
            context.register_source(run_id, "output", output)

            if self.config.interrupt and self.config.interrupt.after:
                logging.info("[task-%s] Job '%s:%s' interrupted at 'after' phase.", context.workflow.task_id, self.id, context.workflow.workflow_id)
                context.register_source(run_id, "job", { "input": input, "output": output })
                answer = await self._interrupt(context, run_id, "after", self.config.interrupt.after)
                if answer is not None:
                    output = answer
                context.register_source(run_id, "output", output)

            logging.debug("[task-%s] Run '%s:%s' for job '%s:%s' completed in %.2f seconds.", context.workflow.task_id, run_id, component.id, self.id, context.workflow.workflow_id, job_time_tracker.elapsed())

            output = (await context.render_variable(run_id, self.config.output)) if self.config.output else output
            outputs.append(output)

        repeat_count = (await context.render_variable(None, self.config.repeat_count)) if self.config.repeat_count else None
        await asyncio.gather(*[ _run_once(input) for _ in range(int(repeat_count or 1)) ])

        output = outputs[0] if len(outputs) == 1 else outputs or None
        context.register_source(None, "output", output)

        return output

    async def _interrupt(self, context: JobContext, run_id: str, phase: str, point: ComponentInterruptPointConfig) -> Any:
        if point.condition:
            input  = await context.render_variable(run_id, point.condition.input)
            value  = await context.render_variable(run_id, point.condition.value)
            if not evaluate_condition(point.condition.operator, input, value):
                logging.debug("[task-%s] Job '%s:%s' interrupt at '%s' phase skipped: condition not met.", context.workflow.task_id, self.id, context.workflow.workflow_id, phase)
                return None

        message  = (await context.render_variable(run_id, point.message))  if point.message  else None
        metadata = (await context.render_variable(run_id, point.metadata)) if point.metadata else None

        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        future = loop.create_future()

        point = InterruptPoint(
            task_id=context.workflow.task_id,
            job_id=self.id,
            phase=phase,
            message=message,
            metadata=metadata,
            future=future
        )

        return await context.workflow.interrupt_handler.interrupt(point)

    def _create_component(self, id: str, component: Union[ComponentConfig, str]) -> ComponentService:
        return create_component(*self._resolve_component(id, component), self.global_configs, daemon=False)

    def _resolve_component(self, id: str, component: Union[ComponentConfig, str]) -> Tuple[str, ComponentConfig]:
        if isinstance(component, str):
            return ComponentResolver(self.global_configs.components).resolve(component)

        return id, component
