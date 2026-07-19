from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TextRerankingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
import asyncio

class TextRerankingTaskAction:
    def __init__(self, config: TextRerankingModelActionConfig):
        self.config: TextRerankingModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        query            = await context.render_text(self.config.query)
        documents        = await context.render_variable(self.config.documents)
        document_field   = await context.render_variable(self.config.document_field) if self.config.document_field is not None else None
        top_k            = await context.render_variable(self.config.top_k) if self.config.top_k is not None else None
        score_threshold  = await context.render_variable(self.config.score_threshold) if self.config.score_threshold is not None else None
        return_documents = await context.render_variable(self.config.return_documents)
        batch_size       = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(query, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        # Wrap a single (query, documents) pair as one reranking job. The tuple zip
        # below would otherwise broadcast the scalar query across each document,
        # yielding one rerank per document instead of one rerank over all documents.
        query     = [ query ] if is_single_input else query
        documents = [ documents ] if is_single_input else documents

        if isinstance(query, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_queries, batch_documents in BatchSourceIterator((query, documents), batch_size=batch_size or 1):
                    batch_texts = self._extract_document_texts(batch_documents, document_field)
                    batch_scores = await self._rerank(batch_queries, batch_texts, params, loop, context.cancellation_token)
                    for scores, original_documents in zip(batch_scores, batch_documents):
                        yield self._build_ranked_result(scores, original_documents, top_k, score_threshold, return_documents)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_queries, batch_documents in BatchSourceIterator((query, documents), batch_size=batch_size or 1):
                batch_texts = self._extract_document_texts(batch_documents, document_field)
                batch_scores = await self._rerank(batch_queries, batch_texts, params, loop, context.cancellation_token)
                for scores, original_documents in zip(batch_scores, batch_documents):
                    results.append(self._build_ranked_result(scores, original_documents, top_k, score_threshold, return_documents))

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length = await context.render_variable(self.config.max_input_length) if self.config.max_input_length is not None else None
        normalize        = await context.render_variable(self.config.params.normalize)

        return {
            "max_input_length": max_input_length,
            "normalize":        normalize,
        }

    def _extract_document_texts(self, batch_documents: List[Any], field: Optional[str]) -> List[List[str]]:
        batch_texts: List[List[str]] = []

        for index, documents in enumerate(batch_documents):
            if not isinstance(documents, list):
                batch_documents[index] = documents = [ documents ]
            batch_texts.append([ self._select_document_text(document, field) for document in documents ])

        return batch_texts

    def _select_document_text(self, document: Any, field: Optional[str]) -> str:
        if isinstance(document, str):
            return document

        if isinstance(document, dict):
            if not field:
                raise ValueError("document_field must be set when documents are objects.")
            return document[field]

        raise TypeError(f"Unsupported document element type: {type(document).__name__}")

    def _build_ranked_result(
        self,
        scores: List[float],
        documents: List[Any],
        top_k: Optional[int],
        score_threshold: Optional[float],
        return_documents: bool,
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []

        for index, score in enumerate(scores):
            item: Dict[str, Any] = { "index": index, "score": float(score) }
            if return_documents:
                item["document"] = documents[index]
            result.append(item)

        result.sort(key=lambda item: item["score"], reverse=True)

        if score_threshold is not None:
            result = [ item for item in result if item["score"] >= float(score_threshold) ]

        if top_k is not None:
            result = result[:int(top_k)]

        return result

    @abstractmethod
    async def _rerank(
        self,
        queries: List[str],
        documents: List[List[str]],
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[List[float]]:
        pass

class TextRerankingTaskService(ModelTaskService):
    pass
