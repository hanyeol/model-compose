from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TypedDecisionModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class TypedDecisionTaskAction(ComponentAction):
    def __init__(self, config: TypedDecisionModelActionConfig):
        self.config: TypedDecisionModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        text       = await context.render_variable(self.config.text)
        schema     = await context.render_variable(self.config.schema_)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(text, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._score_batch(batch_texts, schema, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            texts = [ text ] if is_single_input else text
            results: List[Any] = []
            async for batch_texts in BatchSourceIterator(texts, batch_size=batch_size or 1):
                batch_results = await self._score_batch(batch_texts, schema, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {
            "return_probabilities": await context.render_variable(self.config.return_probabilities),
            "return_logits":        await context.render_variable(self.config.return_logits),
        }

    @abstractmethod
    async def _score_batch(
        self,
        texts: List[str],
        schema: Dict[str, Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        pass
