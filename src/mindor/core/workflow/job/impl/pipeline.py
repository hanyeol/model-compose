from typing import Type, Union, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.job import PipelineJobConfig, InlineJobConfig, ComponentJobConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import JobType, JobContext, RoutingTarget, register_job
from .common import CompositeJob
import asyncio, ulid

@register_job(JobType.PIPELINE)
class PipelineJob(CompositeJob):
    def __init__(self, id: str, config: PipelineJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        components: List[Optional[ComponentService]] = []

        for step in self.config.steps:
            if isinstance(step, ComponentJobConfig):
                components.append(await self._create_component(self.id, step.component))
            else:
                components.append(None)

        input = await context.render_variable(None, self.config.input)

        await self._started(input)

        input = await self._before_run(context, None, input)
        cancellation_token = context.cancellation_token

        is_direct_output = not self.config.output or self.config.output == "${output}"
        last_step_index = len(self.config.steps) - 1

        output: Any = None

        for index, step in enumerate(self.config.steps):
            is_last_step = bool(index == last_step_index)
            output = await self._run_step(step, index, components[index], input, output, context, is_last=is_last_step)

            if cancellation_token is not None and cancellation_token.is_cancelled():
                raise asyncio.CancelledError(cancellation_token.reason or "cancelled")

        output = await self._after_run(context, None, input, output)

        if not is_direct_output:
            context.register_source(None, "output", output)
            output = await context.render_variable(None, self.config.output, skip_decode=context.is_terminal)

        return output

    async def _run_step(
        self,
        step: InlineJobConfig,
        index: int,
        component: Optional[ComponentService],
        pipeline_input: Any,
        previous_output: Any,
        context: JobContext,
        is_last: bool,
    ) -> Any:
        run_id: str = ulid.ulid()
        context.workflow.record_run_id(self.id, run_id)

        job_time_tracker = TimeTracker()
        logging.debug(
            "[task-%s] Step %d '%s' for job '%s:%s' started.",
            context.workflow.task_id,
            index,
            run_id,
            self.id,
            context.workflow.workflow_id,
        )

        is_direct_output = not step.output or step.output == "${output}"
        is_terminal_job = context.is_terminal if is_last else False

        try:
            context.register_source(run_id, "input", pipeline_input)

            if index > 0:
                context.register_source(run_id, "output", previous_output)

            if component is not None:
                if step.input is not None:
                    input = await context.render_variable(run_id, step.input)
                else:
                    input = previous_output if index > 0 else pipeline_input
            else:
                input = previous_output if index > 0 else pipeline_input

            # Expose this step's metadata (received input, position) for the output mapping.
            context.register_source(run_id, "step", { "input": input, "index": index })

            if component is not None:
                output = await component.run(step.action, run_id, input, workflow=context.workflow, job_id=self.id)
            else:
                output = await self._run_inline_job(step, context, run_id, f"step:{index}")

            # Overwrite `${output}` with what this step just produced so the output mapping sees it.
            context.register_source(run_id, "output", output)

            logging.debug(
                "[task-%s] Step %d '%s' for job '%s:%s' completed in %.2f seconds.",
                context.workflow.task_id,
                index,
                run_id,
                self.id,
                context.workflow.workflow_id,
                job_time_tracker.elapsed(),
            )

            return (await context.render_variable(run_id, step.output, skip_decode=is_terminal_job)) if not is_direct_output else output
        finally:
            context._sources.pop(run_id, None)
