from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TextRerankingModelActionConfig
from mindor.core.foundation.variable.text import TextArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction

class TextRerankingTaskAction(ModelTaskComponentAction):
    def __init__(self, config: TextRerankingModelActionConfig):
        self.config: TextRerankingModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        query           = await context.render_text(self.config.query)
        texts           = await context.render_text_array(self.config.texts, item_is_list=True, single_as_array=True)
        top_k           = await context.render_variable(self.config.top_k)
        score_threshold = await context.render_variable(self.config.score_threshold)
        batch_size      = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(query, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(query, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_queries, batch_texts in BatchSourceIterator((query, texts), batch_size=1):
                    # BatchSourceIterator packs each tick into a length-1 batch; the
                    # reranker API takes one (query, texts) pair, so unpack here.
                    scores = await self._rerank(batch_queries[0], batch_texts[0], batch_size or 1, params, context.cancellation_token)
                    result = self._build_ranked_result(scores, top_k, score_threshold)
                    context.register_source("result", result)
                    yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(query, StreamChunkIterator) and query.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_queries, batch_texts in BatchSourceIterator((query, texts), batch_size=1):
                # BatchSourceIterator packs each tick into a length-1 batch; the
                # reranker API takes one (query, texts) pair, so unpack here.
                scores = await self._rerank(batch_queries[0], batch_texts[0], batch_size or 1, params, context.cancellation_token)
                results.append(self._build_ranked_result(scores, top_k, score_threshold))

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length = await context.render_variable(self.config.max_input_length)
        normalize        = await context.render_variable(self.config.params.normalize)

        return {
            "max_input_length": max_input_length,
            "normalize":        normalize,
        }

    def _build_ranked_result(
        self,
        scores: List[float],
        top_k: Optional[int],
        score_threshold: Optional[float],
    ) -> List[Dict[str, Any]]:
        result = [ { "index": index, "score": float(score) } for index, score in enumerate(scores) ]
        result.sort(key=lambda item: item["score"], reverse=True)

        if score_threshold is not None:
            result = [ item for item in result if item["score"] >= float(score_threshold) ]

        if top_k is not None:
            result = result[:int(top_k)]

        return result

    # Not `_rerank_batch` like sibling tasks: reranking has no job-axis batching
    # (each call is one query + its candidates). `batch_size` chunks the (query,
    # text) pair axis inside a single call to cap attention memory.
    @abstractmethod
    async def _rerank(
        self,
        query: str,
        texts: TextArrayValue,
        batch_size: int,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[float]:
        pass
