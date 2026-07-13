from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.job import FilterJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.evaluator.condition import evaluate_condition
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job

@register_job(JobType.FILTER)
class FilterJob(Job):
    config: FilterJobConfig

    def __init__(self, id: str, config: FilterJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input     = await context.render_variable(None, self.config.input)
        streaming = await context.render_variable(None, self.config.streaming)

        input = await self._before_run(context, None, input)

        is_single_input  = not isinstance(input, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${output[]}"

        if isinstance(input, (StreamIterator, AsyncIterator)) or (streaming and not is_single_input):
            async def _stream_output_generator(source=input):
                index = 0
                async for batch_items in BatchSourceIterator(source, batch_size=1):
                    for item in batch_items:
                        if self.config.where is None or await self._matches(context, item, index):
                            context.register_source(self.id, "output[]", item)
                            yield (await context.render_variable(self.id, self.config.output)) if not is_direct_output else item
                        index += 1

            return StreamChunkIterator(_stream_output_generator(), is_fragmented=False)
        else:
            results: List[Any] = []
            index = 0
            async for batch_items in BatchSourceIterator(input, batch_size=1):
                for item in batch_items:
                    if self.config.where is None or await self._matches(context, item, index):
                        context.register_source(self.id, "output[]", item)
                        results.append((await context.render_variable(self.id, self.config.output)) if not is_direct_output else item)
                    index += 1

            output = results[0] if is_single_input else results
            output = await self._after_run(context, None, input, output)

            return output

    async def _matches(self, context: JobContext, item: Any, index: int) -> bool:
        context.register_source(self.id, "item", item)
        context.register_source(self.id, "index", index)

        input = await context.render_variable(self.id, self.config.where.input)
        value = await context.render_variable(self.id, self.config.where.value)

        return evaluate_condition(self.config.where.operator, input, value)
