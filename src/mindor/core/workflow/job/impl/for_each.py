from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.job import ForEachJobConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentService, ComponentGlobalConfigs, ComponentResolver, create_component
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.streaming.iterators import StreamChunkIterator
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job
import asyncio, ulid

@register_job(JobType.FOR_EACH)
class ForEachJob(Job):
    def __init__(self, id: str, config: ForEachJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        component: ComponentService = self._create_component(self.id, self.config.do.component)

        if not component.started:
            await component.start()

        input      = await context.render_variable(None, self.config.input)
        batch_size = await context.render_variable(None, self.config.batch_size)

        if isinstance(input, StreamChunkIterator):
            async def _stream_input_generator(stream=input):
                async for chunk in stream:
                    yield chunk
            input = _stream_input_generator()

        is_single_input = not isinstance(input, (list, AsyncIterator))

        if isinstance(input, AsyncIterator):
            async def _stream_output_generator():
                async for batch_items in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_results = await self._run_batch(batch_items, component, context)
                    for result in batch_results:
                        yield result

            output = _stream_output_generator()
        else:
            results = []
            async for batch_items in BatchSourceIterator(input, batch_size=batch_size or 1):
                results.extend(await self._run_batch(batch_items, component, context))

            output = results[0] if is_single_input else results

        context.register_source(None, "output", output)

        return (await context.render_variable(None, self.config.output, skip_decode=context.is_terminal)) if self.config.output else output

    async def _run_batch(self, batch_items: List[Any], component: ComponentService, context: JobContext) -> List[Any]:
        return await asyncio.gather(*[ self._run(item, component, context) for item in batch_items ])

    async def _run(self, item: Any, component: ComponentService, context: JobContext) -> Any:
        run_id: str = ulid.ulid()
        context.workflow.record_run_id(self.id, run_id)

        job_time_tracker = TimeTracker()
        logging.debug("[task-%s] Run '%s:%s' for job '%s:%s' started.", context.workflow.task_id, run_id, component.id, self.id, context.workflow.workflow_id)

        context.register_source(run_id, "item", item)
        input = (await context.render_variable(run_id, self.config.do.input)) if self.config.do.input is not None else item

        output = await component.run(self.config.do.action, run_id, input, workflow=context.workflow, job_id=self.id)
        context.register_source(run_id, "output", output)

        logging.debug("[task-%s] Run '%s:%s' for job '%s:%s' completed in %.2f seconds.", context.workflow.task_id, run_id, component.id, self.id, context.workflow.workflow_id, job_time_tracker.elapsed())

        return (await context.render_variable(run_id, self.config.do.output, skip_decode=context.is_terminal)) if self.config.do.output else output

    def _create_component(self, id: str, component: Union[ComponentConfig, str]) -> ComponentService:
        return create_component(*self._resolve_component(id, component), self.global_configs, daemon=False)

    def _resolve_component(self, id: str, component: Union[ComponentConfig, str]) -> Tuple[str, ComponentConfig]:
        if isinstance(component, str):
            return ComponentResolver(self.global_configs.components).resolve(component)

        return id, component
