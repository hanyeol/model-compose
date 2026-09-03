from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import FileStoreActionConfig, FileStoreActionMethod
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import ComponentActionContext
from ....action.base import ComponentAction
import asyncio

class FileStoreAction(ComponentAction):
    def __init__(self, config: FileStoreActionConfig):
        self.config: FileStoreActionConfig = config

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
        method: FileStoreActionMethod,
        context: ComponentActionContext,
    ) -> Tuple[Any, bool, bool]:
        if method == FileStoreActionMethod.PUT:
            path   = await context.render_variable(self.config.path)
            source = await context.render_variable(self.config.source)

            is_single_input    = not isinstance(path, (list, StreamIterator, AsyncIterator))
            is_streaming_input = isinstance(path, (StreamIterator, AsyncIterator))

            if is_single_input:
                # Collect mode: one path, source written to that single file. Wrap both as
                # single-element lists so BatchSourceIterator zips them into one _put call
                # instead of iterating a source stream chunk-by-chunk as separate files.
                path, source = [ path ], [ source ]

            return (path, source), is_single_input, is_streaming_input

        if method in (
            FileStoreActionMethod.GET,
            FileStoreActionMethod.DELETE,
            FileStoreActionMethod.EXISTS,
            FileStoreActionMethod.LIST
        ):
            path = await context.render_variable(self.config.path)

            is_single_input    = not isinstance(path, (list, StreamIterator, AsyncIterator))
            is_streaming_input = isinstance(path, (StreamIterator, AsyncIterator))

            return (path,), is_single_input, is_streaming_input

        raise ValueError(f"Unsupported file store action method: {method}")

    async def _resolve_params(
        self,
        method: FileStoreActionMethod,
        context: ComponentActionContext,
    ) -> Dict[str, Any]:
        if method == FileStoreActionMethod.PUT:
            content_type        = await context.render_variable(self.config.content_type)
            metadata            = await context.render_variable(self.config.metadata)
            multipart_threshold = await context.render_scalar(self.config.multipart_threshold, "size")
            chunk_size          = await context.render_scalar(self.config.chunk_size, "size")

            return {
                "content_type":        content_type,
                "metadata":            metadata,
                "multipart_threshold": multipart_threshold,
                "chunk_size":          chunk_size,
            }

        if method == FileStoreActionMethod.GET:
            save_to    = await context.render_variable(self.config.save_to)
            streaming  = await context.render_variable(self.config.streaming)
            chunk_size = await context.render_scalar(self.config.chunk_size, "size")

            return {
                "save_to":    save_to,
                "streaming":  streaming,
                "chunk_size": chunk_size,
            }

        if method in (FileStoreActionMethod.DELETE, FileStoreActionMethod.EXISTS):
            return {}

        if method == FileStoreActionMethod.LIST:
            recursive        = await context.render_variable(self.config.recursive)
            pattern          = await context.render_variable(self.config.pattern)
            max_result_count = await context.render_variable(self.config.max_result_count)
            next_token       = await context.render_variable(self.config.next_token)

            return {
                "recursive":        recursive,
                "pattern":          pattern,
                "max_result_count": max_result_count,
                "next_token":       next_token,
            }

        raise ValueError(f"Unsupported file store action method: {method}")

    async def _process_batch(
        self,
        method: FileStoreActionMethod,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        return await asyncio.gather(*[
            self._process(method, input, params, cancellation_token) for input in inputs
        ])

    async def _process(
        self,
        method: FileStoreActionMethod,
        input: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if method == FileStoreActionMethod.PUT:
            return await self._put(*input, params=params, cancellation_token=cancellation_token)

        if method == FileStoreActionMethod.GET:
            return await self._get(*input, params=params, cancellation_token=cancellation_token)

        if method == FileStoreActionMethod.DELETE:
            return await self._delete(*input, params=params, cancellation_token=cancellation_token)

        if method == FileStoreActionMethod.EXISTS:
            return await self._exists(*input, params=params, cancellation_token=cancellation_token)

        if method == FileStoreActionMethod.LIST:
            return await self._list(*input, params=params, cancellation_token=cancellation_token)

        raise ValueError(f"Unsupported file store action method: {method}")

    @abstractmethod
    async def _put(
        self,
        path: Any,
        source: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _get(
        self,
        path: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(
        self,
        path: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _exists(
        self,
        path: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _list(
        self,
        path: Any,
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass
