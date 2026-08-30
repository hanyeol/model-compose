from typing import Type, Union, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.job import AccumulateJobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs, ComponentResolver, create_component
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
import asyncio, ulid

@register_job(JobType.ACCUMULATE)
class AccumulateJob(Job):
    def __init__(self, id: str, config: AccumulateJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        component: ComponentService = self._create_component(self.id, self.config.do.component)

        if not component.started:
            await component.start()

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

    async def _run_item(self, item: Any, index: int, accumulator: Any, component: ComponentService, context: JobContext) -> Any:
        run_id: str = ulid.ulid()
        context.workflow.record_run_id(self.id, run_id)

        iteration_time_tracker = TimeTracker()
        logging.debug(
            "[task-%s] Iteration %d '%s:%s' for job '%s:%s' started.",
            context.workflow.task_id,
            index,
            run_id,
            component.id,
            self.id,
            context.workflow.workflow_id,
        )

        is_direct_output = not self.config.do.output or self.config.do.output == "${output}"

        try:
            context.register_source(run_id, "item", item)
            context.register_source(run_id, "accumulator", accumulator)

            if self.config.do.input is not None:
                input = await context.render_variable(run_id, self.config.do.input)
            else:
                input = item

            output = await component.run(self.config.do.action, run_id, input, workflow=context.workflow, job_id=self.id)
            context.register_source(run_id, "output", output)

            logging.debug(
                "[task-%s] Iteration %d '%s:%s' for job '%s:%s' completed in %.2f seconds.",
                context.workflow.task_id,
                index,
                run_id,
                component.id,
                self.id,
                context.workflow.workflow_id,
                iteration_time_tracker.elapsed(),
            )

            return (await context.render_variable(run_id, self.config.do.output, skip_decode=context.is_terminal)) if not is_direct_output else output
        finally:
            context._sources.pop(run_id, None)

    def _create_component(self, id: str, component: Union[ComponentConfig, str]) -> ComponentService:
        return create_component(*self._resolve_component(id, component), self.global_configs, daemon=False)

    def _resolve_component(self, id: str, component: Union[ComponentConfig, str]) -> Tuple[str, ComponentConfig]:
        if isinstance(component, str):
            return ComponentResolver(self.global_configs.components).resolve(component)

        return id, component
