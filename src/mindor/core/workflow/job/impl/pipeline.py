from typing import Union, Optional, Any
from mindor.dsl.schema.job import PipelineJobConfig, InlineJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import JobType, JobContext, RoutingTarget, register_job
from .common import CompositeJob
import asyncio, ulid

@register_job(JobType.PIPELINE)
class PipelineJob(CompositeJob):
    def __init__(self, id: str, config: PipelineJobConfig, global_configs: ComponentGlobalConfigs):
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
        cancellation_token = context.cancellation_token

        is_direct_output = not self.config.output or self.config.output == "${output}"

        output: Any = None
        last_step_index = len(self.config.steps) - 1

        for index, step in enumerate(self.config.steps):
            if cancellation_token is not None and cancellation_token.is_cancelled():
                raise asyncio.CancelledError(cancellation_token.reason or "cancelled")

            is_last_step = bool(index == last_step_index)
            output = await self._run_step(step, index, input, output, context, is_last=is_last_step, is_terminal=is_terminal)

        output = await self._after_run(context, run_id, input, output)

        if not is_direct_output:
            context.register_source(run_id, "output", output)
            output = await context.render_variable(run_id, self.config.output, skip_decode=is_terminal)

        return output

    async def _run_step(
        self,
        step: InlineJobConfig,
        index: int,
        pipeline_input: Any,
        previous_output: Any,
        context: JobContext,
        is_last: bool,
        is_terminal: bool,
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

        try:
            context.register_source(run_id, "input", pipeline_input)

            if index > 0:
                context.register_source(run_id, "output", previous_output)

            input = previous_output if index > 0 else pipeline_input
            context.register_source(run_id, "step", { "input": input, "index": index })

            output = await self._run_inline_job(
                step,
                context,
                run_id,
                f"step:{index}",
                input=input,
                is_terminal=(is_last and is_terminal),
            )

            logging.debug(
                "[task-%s] Step %d '%s' for job '%s:%s' completed in %.2f seconds.",
                context.workflow.task_id,
                index,
                run_id,
                self.id,
                context.workflow.workflow_id,
                job_time_tracker.elapsed(),
            )

            return output
        finally:
            context._sources.pop(run_id, None)
