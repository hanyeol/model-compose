from typing import Type, Union, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.job import AccumulateJobConfig, ComponentJobConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import JobType, JobContext, RoutingTarget, register_job
from .common import CompositeJob
import asyncio, ulid

@register_job(JobType.ACCUMULATE)
class AccumulateJob(CompositeJob):
    def __init__(self, id: str, config: AccumulateJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        component: Optional[ComponentService] = None

        if isinstance(self.config.do, ComponentJobConfig):
            component = await self._create_component(self.id, self.config.do.component)

        input       = await context.render_variable(None, self.config.input)
        accumulator = await context.render_variable(None, self.config.accumulator)

        await self._started(input)

        input = await self._before_run(context, None, input)
        cancellation_token = context.cancellation_token

        is_direct_output = not self.config.output or self.config.output == "${output}"

        index = 0
        async for batch_items in BatchSourceIterator(input, batch_size=1):
            for item in batch_items:
                accumulator = await self._run_item(item, index, accumulator, component, context)
                index += 1

                if cancellation_token is not None and cancellation_token.is_cancelled():
                    raise asyncio.CancelledError(cancellation_token.reason or "cancelled")

        output = await self._after_run(context, None, input, accumulator)

        if not is_direct_output:
            context.register_source(None, "output", output)
            output = await context.render_variable(None, self.config.output, skip_decode=context.is_terminal)

        return output

    async def _run_item(
        self,
        item: Any,
        index: int,
        accumulator: Any,
        component: Optional[ComponentService],
        context: JobContext
    ) -> Any:
        run_id: str = ulid.ulid()
        context.workflow.record_run_id(self.id, run_id)

        job_time_tracker = TimeTracker()
        logging.debug(
            "[task-%s] Iteration %d '%s' for job '%s:%s' started.",
            context.workflow.task_id,
            index,
            run_id,
            self.id,
            context.workflow.workflow_id,
        )

        is_direct_output = not self.config.do.output or self.config.do.output == "${output}"

        try:
            context.register_source(run_id, "item", item)
            context.register_source(run_id, "accumulator", accumulator)

            if component is not None:
                if self.config.do.input is not None:
                    input = await context.render_variable(run_id, self.config.do.input)
                else:
                    input = item
                output = await component.run(self.config.do.action, run_id, input, workflow=context.workflow, job_id=self.id)
            else:
                output = await self._run_inline_job(self.config.do, context, run_id, "do")

            context.register_source(run_id, "output", output)

            logging.debug(
                "[task-%s] Iteration %d '%s' for job '%s:%s' completed in %.2f seconds.",
                context.workflow.task_id,
                index,
                run_id,
                self.id,
                context.workflow.workflow_id,
                job_time_tracker.elapsed(),
            )

            return (await context.render_variable(run_id, self.config.do.output, skip_decode=context.is_terminal)) if not is_direct_output else output
        finally:
            context._sources.pop(run_id, None)
