from __future__ import annotations

from typing import Union, Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import DocumentLoaderActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class DocumentLoaderAction(ComponentAction):
    def __init__(self, config: DocumentLoaderActionConfig, context: ComponentActionContext):
        self.config: DocumentLoaderActionConfig = config
        self.context: ComponentActionContext = context

    async def run(self) -> Any:
        source     = await self.context.render_variable(self.config.source)
        batch_size = await self.context.render_variable(self.config.batch_size)
        streaming  = await self.context.render_variable(self.config.streaming)

        params = await self._resolve_params()

        is_single_input  = not isinstance(source, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(source, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._load_batch(batch_sources, params, streaming, self.context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    self.context.register_source("result[]", chunk, scope=scope)
                                    yield (await self.context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._load_batch(batch_sources, params, streaming, self.context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                self.context.register_source("result[]", chunk, scope=scope)
                                yield (await self.context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            self.context.register_source("result", result)

            return (await self.context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    async def _resolve_params(self) -> Dict[str, Any]:
        return {}

    async def _resolve_source_path(self, source: Any, extension: Optional[str]) -> Tuple[str, bool]:
        """Turn any accepted source shape into a filesystem path.

        Returns ``(path, spooled)``. When ``spooled`` is True the caller must
        remove ``path`` after use. ``extension`` is used as the spool file's
        suffix; drivers pass the format they expect (e.g. ``".pdf"``).
        """
        stream = await resolve_stream_resource(source)

        if isinstance(stream, FileStreamResource):
            return stream.path, False

        spooled_path = await save_stream_to_temporary_file(stream, extension)

        return spooled_path, True

    @abstractmethod
    async def _load_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]]:
        """Load one batch of sources and return one parsed document entry per source.

        When ``streaming`` is False each entry is a dict with shape:
        ``{ text, source, index, driver, meta, ... }`` for a single-chunk
        document, or ``{ chunks: [...], source, driver, meta }`` for a whole
        document. When ``streaming`` is True each entry is an async iterator
        yielding per-chunk dicts as they are produced.
        """
        pass
