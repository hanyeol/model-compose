from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import KeyValueStoreActionConfig, KeyValueStoreActionMethod
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import asyncio

class KeyValueStoreAction(ComponentAction):
    def __init__(self, config: KeyValueStoreActionConfig):
        self.config: KeyValueStoreActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, primary_input, is_single_input, is_streaming_input = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                    batch_results = await self._process_batch(self.config.method, batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(primary_input, StreamChunkIterator) and primary_input.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_inputs = zip(*batch_inputs) # Transpose per-slot batches into per-request tuples.
                batch_results = await self._process_batch(self.config.method, batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(
        self,
        method: KeyValueStoreActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, Any, bool, bool]:
        if method == KeyValueStoreActionMethod.SET:
            keys = _as_batch_array(await context.render_variable(self.config.key))

            # A single-key SET stores the raw value intact (a list value becomes
            # one stored value, not per-key entries). Multi-key SET expects
            # `value` to be a matching list.
            if isinstance(keys, ArrayValue) and keys.is_single:
                values = ArrayValue([ await context.render_variable(self.config.value) ], is_single=True)
            else:
                values = _as_batch_array(await context.render_variable(self.config.value))

            primary_input      = next((value for value in (keys, values) if isinstance(value, (StreamIterator, AsyncIterator))), None)
            is_single_input    = isinstance(keys, ArrayValue) and keys.is_single
            is_streaming_input = primary_input is not None

            return (keys, values), primary_input, is_single_input, is_streaming_input

        if method in (
            KeyValueStoreActionMethod.GET,
            KeyValueStoreActionMethod.DELETE,
            KeyValueStoreActionMethod.EXISTS,
        ):
            keys = _as_batch_array(await context.render_variable(self.config.key))

            is_single_input    = isinstance(keys, ArrayValue) and keys.is_single
            is_streaming_input = isinstance(keys, (StreamIterator, AsyncIterator))

            return (keys,), keys, is_single_input, is_streaming_input

        raise ValueError(f"Unsupported key-value store action method: {method}")

    async def _resolve_params(
        self,
        method: KeyValueStoreActionMethod,
        context: ComponentActionContext,
    ) -> Dict[str, Any]:
        if method == KeyValueStoreActionMethod.SET:
            ttl = await context.render_scalar(self.config.ttl, "time")

            return { "ttl": ttl }

        if method in (
            KeyValueStoreActionMethod.GET,
            KeyValueStoreActionMethod.DELETE,
            KeyValueStoreActionMethod.EXISTS,
        ):
            return {}

        raise ValueError(f"Unsupported key-value store action method: {method}")

    async def _process_batch(
        self,
        method: KeyValueStoreActionMethod,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[Dict[str, Any]]]:
        # Each `_process` call maps to one native-batch driver call and returns
        # a `List[Dict]` (one entry per key in that request). Preserve the
        # grouping so one request stays one `${result}`.
        return await asyncio.gather(*[
            self._process(method, input, params, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: KeyValueStoreActionMethod,
        input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        async def _collect(value: Any) -> Any:
            return await value.collect() if value is not None else None

        input = tuple(await asyncio.gather(*[ _collect(value) for value in input ]))

        if method == KeyValueStoreActionMethod.SET:
            keys, values = input

            # Broadcast a single value across all keys; otherwise pair by position.
            if len(values) == 1 and len(keys) > 1:
                values = [ values[0] ] * len(keys)

            if len(keys) != len(values):
                raise ValueError(f"key/value cardinality mismatch: {len(keys)} keys vs {len(values)} values.")

            if not keys:
                return []

            return await self._set(keys, values, params=params, cancellation_token=cancellation_token)

        if method == KeyValueStoreActionMethod.GET:
            keys, = input

            if not keys:
                return []

            return await self._get(keys, params=params, cancellation_token=cancellation_token)

        if method == KeyValueStoreActionMethod.DELETE:
            keys, = input

            if not keys:
                return []

            return await self._delete(keys, params=params, cancellation_token=cancellation_token)

        if method == KeyValueStoreActionMethod.EXISTS:
            keys, = input

            if not keys:
                return []

            return await self._exists(keys, params=params, cancellation_token=cancellation_token)

        raise ValueError(f"Unsupported key-value store action method: {method}")

    @abstractmethod
    async def _get(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _set(
        self,
        keys: List[str],
        values: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _delete(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _exists(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        pass

def _as_batch_array(value: Any) -> Any:
    # KV store treats a flat list as the keys of one native-batch call
    # (MGET/MSET/pipelined DEL/EXISTS), not per-element requests. A scalar
    # degenerates to a single-key batch flagged ``is_single`` so the caller
    # can unwrap the result shape.
    if value is None or isinstance(value, (StreamIterator, AsyncIterator)):
        return value

    if isinstance(value, (list, tuple)):
        return ArrayValue(list(value), is_single=False)

    return ArrayValue([ value ], is_single=True)
