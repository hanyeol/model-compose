from __future__ import annotations

from typing import Union, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.vector import VectorArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
from ....action.base import ComponentAction
import asyncio

class VectorStoreAction(ComponentAction):
    def __init__(self, config: VectorStoreActionConfig, client: Any):
        self.config: VectorStoreActionConfig = config
        self.client: Any = client

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        collection = await self._resolve_collection(self.config.method, context)
        params     = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                    batch_results = await self._process_batch(self.config.method, collection, batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                batch_results = await self._process_batch(self.config.method, collection, batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: VectorStoreActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        if method == VectorStoreActionMethod.INSERT:
            vectors    = await context.render_vector_array(self.config.vector, single_as_array=True)
            vector_ids = await context.render_array(self.config.vector_id, single_as_array=True)
            metadatas  = await context.render_array(self.config.metadata, single_as_array=True)

            is_single_input    = isinstance(vectors, VectorArrayValue) and vectors.is_single
            is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (vectors, vector_ids, metadatas))

            return (vector_ids, vectors, metadatas), is_single_input, is_streaming_input

        if method == VectorStoreActionMethod.UPDATE:
            vector_ids = await context.render_array(self.config.vector_id, single_as_array=True)
            vectors    = await context.render_vector_array(self.config.vector, single_as_array=True)
            metadatas  = await context.render_array(self.config.metadata, single_as_array=True)

            is_single_input    = isinstance(vector_ids, ArrayValue) and vector_ids.is_single
            is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (vector_ids, vectors, metadatas))

            return (vector_ids, vectors, metadatas), is_single_input, is_streaming_input

        if method == VectorStoreActionMethod.SEARCH:
            queries = await context.render_vector_array(self.config.query, single_as_array=True)

            is_single_input    = isinstance(queries, VectorArrayValue) and queries.is_single
            is_streaming_input = isinstance(queries, (StreamIterator, AsyncIterator))

            return (queries,), is_single_input, is_streaming_input

        if method == VectorStoreActionMethod.DELETE:
            vector_ids = await context.render_array(self.config.vector_id, single_as_array=True)

            is_single_input    = isinstance(vector_ids, ArrayValue) and vector_ids.is_single
            is_streaming_input = isinstance(vector_ids, (StreamIterator, AsyncIterator))

            return (vector_ids,), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported vector store action method: {method}")

    async def _resolve_collection(self, method: VectorStoreActionMethod, context: ComponentActionContext) -> Any:
        return await context.render_variable(self.config.collection)

    async def _resolve_params(self, method: VectorStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == VectorStoreActionMethod.INSERT:
            id_field     = await context.render_variable(self.config.id_field)
            vector_field = await context.render_variable(self.config.vector_field)

            return {
                "id_field":     id_field,
                "vector_field": vector_field,
            }

        if method == VectorStoreActionMethod.UPDATE:
            id_field            = await context.render_variable(self.config.id_field)
            vector_field        = await context.render_variable(self.config.vector_field)
            insert_if_not_exist = await context.render_scalar(self.config.insert_if_not_exist, bool)

            return {
                "id_field":            id_field,
                "vector_field":        vector_field,
                "insert_if_not_exist": insert_if_not_exist,
            }

        if method == VectorStoreActionMethod.SEARCH:
            vector_field  = await context.render_variable(self.config.vector_field)
            top_k         = await context.render_variable(self.config.top_k)
            filter        = await context.render_variable(self.config.filter)
            output_fields = await context.render_variable(self.config.output_fields)

            return {
                "vector_field":  vector_field,
                "top_k":         top_k,
                "filter":        filter,
                "output_fields": output_fields,
            }

        if method == VectorStoreActionMethod.DELETE:
            id_field = await context.render_variable(self.config.id_field)
            filter   = await context.render_variable(self.config.filter)

            return {
                "id_field": id_field,
                "filter":   filter,
            }

        raise ValueError(f"Unsupported vector store action method: {method}")

    async def _process_batch(
        self,
        method: VectorStoreActionMethod,
        collection: Any,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        return await asyncio.gather(*[
            self._process(method, collection, input, params, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: VectorStoreActionMethod,
        collection: Any,
        input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        async def _collect(value: Any) -> Any:
            return await value.collect() if value is not None else None

        input = tuple(await asyncio.gather(*[ _collect(value) for value in input ]))

        if method == VectorStoreActionMethod.INSERT:
            return await self._insert(collection, *input, params=params, cancellation_token=cancellation_token)

        if method == VectorStoreActionMethod.UPDATE:
            return await self._update(collection, *input, params=params, cancellation_token=cancellation_token)

        if method == VectorStoreActionMethod.SEARCH:
            return await self._search(collection, *input, params=params, cancellation_token=cancellation_token)

        if method == VectorStoreActionMethod.DELETE:
            return await self._delete(collection, *input, params=params, cancellation_token=cancellation_token)

        raise ValueError(f"Unsupported vector store action method: {method}")

    @abstractmethod
    async def _insert(
        self,
        collection: Any,
        vector_ids: Optional[List[Any]],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Any:
        pass

    @abstractmethod
    async def _update(
        self,
        collection: Any,
        vector_ids: List[Any],
        vectors: Optional[List[List[float]]],
        metadatas: Optional[List[Dict[str, Any]]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Any:
        pass

    @abstractmethod
    async def _search(
        self,
        collection: Any,
        queries: List[List[float]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Any:
        pass

    @abstractmethod
    async def _delete(
        self,
        collection: Any,
        vector_ids: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Any:
        pass
