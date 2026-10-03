from typing import Union, List, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.job import ForEachJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.time import TimeTracker
from mindor.core.logger import logging
from ..base import JobType, JobContext, RoutingTarget, register_job
from .common import CompositeJob
import asyncio, ulid

@register_job(JobType.FOR_EACH)
class ForEachJob(CompositeJob):
    def __init__(self, id: str, config: ForEachJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input      = await context.render_variable(None, self.config.input) if self.config.input is not None else context.default_input
        batch_size = await context.render_variable(None, self.config.batch_size)
        streaming  = await context.render_variable(None, self.config.streaming)

        await self._started(input)

        input = await self._before_run(context, None, input)
        cancellation_token = context.cancellation_token

        is_single_input  = not isinstance(input, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${output}"

        if isinstance(input, (StreamIterator, AsyncIterator)) or (streaming and not is_single_input):
            async def _stream_output_generator(source=input):
                async for batch_items in BatchSourceIterator(source, batch_size=batch_size or 1):
                    if cancellation_token is not None and cancellation_token.is_cancelled():
                        raise asyncio.CancelledError(cancellation_token.reason or "cancelled")

                    batch_results = await self._run_batch(batch_items, context)
                    for result in batch_results:
                        yield result

            is_fragmented = isinstance(input, StreamChunkIterator) and input.is_fragmented
            output = StreamChunkIterator(_stream_output_generator(), is_fragmented=is_fragmented)
        else:
            results = []
            async for batch_items in BatchSourceIterator(input, batch_size=batch_size or 1):
                if cancellation_token is not None and cancellation_token.is_cancelled():
                    raise asyncio.CancelledError(cancellation_token.reason or "cancelled")

                results.extend(await self._run_batch(batch_items, context))

            output = results[0] if is_single_input else results

        output = await self._after_run(context, None, input, output)

        if not is_direct_output:
            context.register_source(None, "output", output)
            output = await context.render_variable(None, self.config.output, skip_decode=context.is_terminal)

        return output

    async def _run_batch(self, batch_items: List[Any], context: JobContext) -> List[Any]:
        return await asyncio.gather(*[
            self._run_item(item, context) for item in batch_items
        ])

    async def _run_item(self, item: Any, context: JobContext) -> Any:
        run_id: str = ulid.ulid()
        context.workflow.record_run_id(self.id, run_id)
        if isinstance(item, dict) and "timestamp" in item:
            print(f"[FOREACH IN] run_id={run_id[-6:]} item.timestamp={item['timestamp']!r:.40}", flush=True)

        job_time_tracker = TimeTracker()
        logging.debug(
            "[task-%s] Run '%s' for job '%s:%s' started.",
            context.workflow.task_id,
            run_id,
            self.id,
            context.workflow.workflow_id,
        )

        try:
            context.register_source(run_id, "item", item)

            output = await self._run_inline_job(self.config.do, context, run_id, "do", input=item)
            if isinstance(output, dict) and "timestamp" in output:
                print(f"[FOREACH OUT] run_id={run_id[-6:]} output.timestamp={output['timestamp']!r:.40}", flush=True)

            logging.debug(
                "[task-%s] Run '%s' for job '%s:%s' completed in %.2f seconds.",
                context.workflow.task_id,
                run_id,
                self.id,
                context.workflow.workflow_id,
                job_time_tracker.elapsed(),
            )

            return output
        finally:
            context._sources.pop(run_id, None)
