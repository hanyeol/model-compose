from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import GraphStoreActionConfig, GraphStoreActionMethod
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
from ....action.base import ComponentAction
import asyncio

class GraphStoreAction(ComponentAction):
    def __init__(self, config: GraphStoreActionConfig, database: Any):
        self.config: GraphStoreActionConfig = config
        self.database: Any = database

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                    batch_results = await self._process_batch(self.config.method, batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                batch_results = await self._process_batch(self.config.method, batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: GraphStoreActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        # INSERT/UPDATE/DELETE deliver the whole node/relationship collection to the
        # driver in one native-batch call. Each ArrayValue travels through
        # BatchSourceIterator as a single unit (ArrayValue is not iterable to the
        # batcher), so the driver receives all items in one request.
        if method == GraphStoreActionMethod.QUERY:
            queries = await context.render_array(self.config.query, single_as_array=True)

            is_single_input    = isinstance(queries, ArrayValue) and queries.is_single
            is_streaming_input = isinstance(queries, (StreamIterator, AsyncIterator))

            return (queries,), is_single_input, is_streaming_input

        # INSERT/UPDATE/DELETE deliver the whole collection to the driver in a
        # single native-batch call. `is_single_input` is True when every present
        # slot carries a single item (an omitted slot doesn't disqualify).
        if method == GraphStoreActionMethod.INSERT:
            nodes         = await context.render_array(self.config.node, single_as_array=True)
            relationships = await context.render_array(self.config.relationship, single_as_array=True)

            is_single_input    = all(value is None or (isinstance(value, ArrayValue) and value.is_single) for value in (nodes, relationships))
            is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (nodes, relationships))

            return (nodes, relationships), is_single_input, is_streaming_input

        if method == GraphStoreActionMethod.UPDATE:
            node_ids         = await context.render_array(self.config.node_id, single_as_array=True)
            relationship_ids = await context.render_array(self.config.relationship_id, single_as_array=True)

            is_single_input    = all(value is None or (isinstance(value, ArrayValue) and value.is_single) for value in (node_ids, relationship_ids))
            is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (node_ids, relationship_ids))

            return (node_ids, relationship_ids), is_single_input, is_streaming_input

        if method == GraphStoreActionMethod.DELETE:
            node_ids         = await context.render_array(self.config.node_id, single_as_array=True)
            relationship_ids = await context.render_array(self.config.relationship_id, single_as_array=True)

            is_single_input    = all(value is None or (isinstance(value, ArrayValue) and value.is_single) for value in (node_ids, relationship_ids))
            is_streaming_input = any(isinstance(value, (StreamIterator, AsyncIterator)) for value in (node_ids, relationship_ids))

            return (node_ids, relationship_ids), is_single_input, is_streaming_input

        if method == GraphStoreActionMethod.TRAVERSE:
            start_nodes = await context.render_array(self.config.start_node, single_as_array=True)

            is_single_input    = isinstance(start_nodes, ArrayValue) and start_nodes.is_single
            is_streaming_input = isinstance(start_nodes, (StreamIterator, AsyncIterator))

            return (start_nodes,), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported graph store action method: {method}")

    async def _resolve_params(self, method: GraphStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == GraphStoreActionMethod.QUERY:
            bind_vars = await context.render_variable(self.config.params)

            return {
                "bind_vars": bind_vars,
            }

        if method == GraphStoreActionMethod.INSERT:
            return {}

        if method == GraphStoreActionMethod.UPDATE:
            properties = await context.render_variable(self.config.properties)
            labels     = await context.render_variable(self.config.labels)

            return {
                "properties": properties,
                "labels":     labels,
            }

        if method == GraphStoreActionMethod.DELETE:
            detach = await context.render_variable(self.config.detach)

            return {
                "detach": detach,
            }

        if method == GraphStoreActionMethod.TRAVERSE:
            direction          = await context.render_variable(self.config.direction)
            max_depth          = await context.render_variable(self.config.max_depth)
            relationship_types = await context.render_variable(self.config.relationship_types)
            node_labels        = await context.render_variable(self.config.node_labels)

            return {
                "direction":          direction,
                "max_depth":          max_depth,
                "relationship_types": relationship_types,
                "node_labels":        node_labels,
            }

        raise ValueError(f"Unsupported graph store action method: {method}")

    async def _process_batch(
        self,
        method: GraphStoreActionMethod,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        return await asyncio.gather(*[
            self._process(method, input, params, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: GraphStoreActionMethod,
        input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        async def _collect(value: Any) -> Any:
            return await value.collect() if value is not None else None

        input = tuple(await asyncio.gather(*[ _collect(value) for value in input ]))

        if method == GraphStoreActionMethod.QUERY:
            return await self._query(*input, params=params, cancellation_token=cancellation_token)

        if method == GraphStoreActionMethod.INSERT:
            return await self._insert(*input, params=params, cancellation_token=cancellation_token)

        if method == GraphStoreActionMethod.UPDATE:
            return await self._update(*input, params=params, cancellation_token=cancellation_token)

        if method == GraphStoreActionMethod.DELETE:
            return await self._delete(*input, params=params, cancellation_token=cancellation_token)

        if method == GraphStoreActionMethod.TRAVERSE:
            return await self._traverse(*input, params=params, cancellation_token=cancellation_token)

        raise ValueError(f"Unsupported graph store action method: {method}")

    @abstractmethod
    async def _query(
        self,
        queries: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _insert(
        self,
        nodes: Optional[List[Dict[str, Any]]],
        relationships: Optional[List[Dict[str, Any]]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _update(
        self,
        node_ids: Optional[List[Any]],
        relationship_ids: Optional[List[Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(
        self,
        node_ids: Optional[List[Any]],
        relationship_ids: Optional[List[Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _traverse(
        self,
        start_nodes: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        pass
