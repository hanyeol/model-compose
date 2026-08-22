from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import SearchEngineActionConfig, SearchEngineActionMethod
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
from ....action.base import ComponentAction
import asyncio

class SearchEngineAction(ComponentAction):
    def __init__(self, config: SearchEngineActionConfig, database: Any):
        self.config: SearchEngineActionConfig = config
        self.database: Any = database

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        index  = await self._resolve_index(self.config.method, context)
        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                    batch_results = await self._process_batch(self.config.method, index, batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                batch_results = await self._process_batch(self.config.method, index, batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: SearchEngineActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        if method == SearchEngineActionMethod.INDEX:
            documents = await context.render_array(self.config.document, single_as_array=True)

            is_single_input    = isinstance(documents, ArrayValue) and documents.is_single
            is_streaming_input = isinstance(documents, (StreamIterator, AsyncIterator))

            return (documents,), is_single_input, is_streaming_input

        if method == SearchEngineActionMethod.SEARCH:
            queries = await context.render_array(self.config.query, single_as_array=True)

            is_single_input    = isinstance(queries, ArrayValue) and queries.is_single
            is_streaming_input = isinstance(queries, (StreamIterator, AsyncIterator))

            return (queries,), is_single_input, is_streaming_input

        if method == SearchEngineActionMethod.DELETE:
            document_ids = await context.render_array(self.config.document_id, single_as_array=True)

            is_single_input    = isinstance(document_ids, ArrayValue) and document_ids.is_single
            is_streaming_input = isinstance(document_ids, (StreamIterator, AsyncIterator))

            return (document_ids,), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported search engine action method: {method}")

    async def _resolve_index(self, method: SearchEngineActionMethod, context: ComponentActionContext) -> Any:
        return await context.render_variable(self.config.index)

    async def _resolve_params(self, method: SearchEngineActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == SearchEngineActionMethod.INDEX:
            fields = self.config.fields

            return {
                "fields": fields,
            }

        if method == SearchEngineActionMethod.SEARCH:
            limit         = await context.render_scalar(self.config.limit, int)
            search_fields = await context.render_variable(self.config.search_fields)

            return {
                "limit":         limit,
                "search_fields": search_fields,
            }

        if method == SearchEngineActionMethod.DELETE:
            return {}

        raise ValueError(f"Unsupported search engine action method: {method}")

    async def _process_batch(
        self,
        method: SearchEngineActionMethod,
        index: Any,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        return await asyncio.gather(*[
            self._process(method, index, input, params, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: SearchEngineActionMethod,
        index: Any,
        input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        async def _collect(value: Any) -> Any:
            return await value.collect() if value is not None else None

        input = tuple(await asyncio.gather(*[ _collect(value) for value in input ]))

        if method == SearchEngineActionMethod.INDEX:
            return await self._index(index, *input, params=params, cancellation_token=cancellation_token)

        if method == SearchEngineActionMethod.SEARCH:
            return await self._search(index, *input, params=params, cancellation_token=cancellation_token)

        if method == SearchEngineActionMethod.DELETE:
            return await self._delete(index, *input, params=params, cancellation_token=cancellation_token)

        raise ValueError(f"Unsupported search engine action method: {method}")

    @abstractmethod
    async def _index(
        self,
        index: Any,
        documents: List[Dict[str, Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _search(
        self,
        index: Any,
        queries: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        pass

    @abstractmethod
    async def _delete(
        self,
        index: Any,
        document_ids: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass
