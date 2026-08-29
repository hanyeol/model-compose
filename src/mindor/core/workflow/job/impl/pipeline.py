from typing import Type, Union, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.job import PipelineJobConfig
from mindor.dsl.schema.job.impl.pipeline import PipelineStepConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs, ComponentResolver, create_component
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
import asyncio, ulid

@register_job(JobType.PIPELINE)
class PipelineJob(Job):
    def __init__(self, id: str, config: PipelineJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input = await context.render_variable(None, self.config.input)

        await self._started(input)

        input = await self._before_run(context, None, input)
        cancellation_token = context.cancellation_token

        is_direct_output = not self.config.output or self.config.output == "${output}"

        output: Any = None

        for index, step in enumerate(self.config.steps):
            output = await self._run_step(step, index, input, output, context)

            if cancellation_token is not None and cancellation_token.is_cancelled():
                raise asyncio.CancelledError(cancellation_token.reason or "cancelled")

        output = await self._after_run(context, None, input, output)

        if not is_direct_output:
            context.register_source(None, "output", output)
            output = await context.render_variable(None, self.config.output, skip_decode=context.is_terminal)

        return output

    async def _run_step(
        self,
        step: PipelineStepConfig,
        index: int,
        pipeline_input: Any,
        previous_output: Any,
        context: JobContext,
    ) -> Any:
        component: ComponentService = self._create_component(self.id, step.component)

        if not component.started:
            await component.start()

        run_id: str = ulid.ulid()
        context.workflow.record_run_id(self.id, run_id)

        step_time_tracker = TimeTracker()
        logging.debug(
            "[task-%s] Step %d '%s:%s' for job '%s:%s' started.",
            context.workflow.task_id,
            index,
            run_id,
            component.id,
            self.id,
            context.workflow.workflow_id,
        )

        is_direct_output = not step.output or step.output == "${output}"

        try:
            context.register_source(run_id, "input", pipeline_input)

            if index > 0:
                context.register_source(run_id, "output", previous_output)

            if step.input is not None:
                input = await context.render_variable(run_id, step.input)
            else:
                input = previous_output if index > 0 else pipeline_input

            output = await component.run(step.action, run_id, input, workflow=context.workflow, job_id=self.id)
            context.register_source(run_id, "output", output)

            logging.debug(
                "[task-%s] Step %d '%s:%s' for job '%s:%s' completed in %.2f seconds.",
                context.workflow.task_id,
                index,
                run_id,
                component.id,
                self.id,
                context.workflow.workflow_id,
                step_time_tracker.elapsed(),
            )

            return (await context.render_variable(run_id, step.output, skip_decode=context.is_terminal)) if not is_direct_output else output
        finally:
            context._sources.pop(run_id, None)

    def _create_component(self, id: str, component: Union[ComponentConfig, str]) -> ComponentService:
        return create_component(*self._resolve_component(id, component), self.global_configs, daemon=False)

    def _resolve_component(self, id: str, component: Union[ComponentConfig, str]) -> Tuple[str, ComponentConfig]:
        if isinstance(component, str):
            return ComponentResolver(self.global_configs.components).resolve(component)

        return id, component
