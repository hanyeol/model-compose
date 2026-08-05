from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.job import FilterJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.evaluator.condition import evaluate_condition, evaluate_where
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ..base import Job, JobType, JobContext, RoutingTarget, register_job

@register_job(JobType.FILTER)
class FilterJob(Job):
    config: FilterJobConfig

    def __init__(self, id: str, config: FilterJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input     = await context.render_variable(None, self.config.input)
        streaming = await context.render_variable(None, self.config.streaming)

        await self._started(input)

        input = await self._before_run(context, None, input)

        is_single_input  = not isinstance(input, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${output}"
        where = self.config.where.model_dump(by_alias=True, exclude_none=True) if self.config.where else None

        if isinstance(input, (StreamIterator, AsyncIterator)) or (streaming and not is_single_input):
            async def _stream_output_generator(source=input):
                index = 0
                async for batch_items in BatchSourceIterator(source, batch_size=1):
                    for item in batch_items:
                        if where is None or await self._matches_where(context, where, item, index):
                            yield item
                        index += 1

            output = _stream_output_generator()
        else:
            results: List[Any] = []
            index = 0
            async for batch_items in BatchSourceIterator(input, batch_size=1):
                for item in batch_items:
                    if where is None or await self._matches_where(context, where, item, index):
                        results.append(item)
                    index += 1

            output = results[0] if is_single_input else results

        output = await self._after_run(context, None, input, output)

        if not is_direct_output:
            context.register_source(None, "output", output)
            output = await context.render_variable(None, self.config.output)

        return output

    async def _matches_where(self, context: JobContext, where: Dict[str, Any], item: Any, index: int) -> bool:
        context.register_source(self.id, "item", item)
        context.register_source(self.id, "index", index)

        async def _evaluate_condition(condition: Dict[str, Any]) -> bool:
            input = await context.render_variable(self.id, condition.get("input"))
            value = await context.render_variable(self.id, condition.get("value"))
            operator = ConditionOperator(condition.get("operator", ConditionOperator.EQ.value))
            return evaluate_condition(operator, input, value)

        return await evaluate_where(where, _evaluate_condition)
