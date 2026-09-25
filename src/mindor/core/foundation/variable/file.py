from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.resources import StreamResource, save_stream_to_temporary_file
from ..streaming.file import FileStreamResource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
import os

class FileArrayValue:
    """A materialized or streaming array of file-backed stream resources.

    Iteration and `collect()` yield raw `StreamResource`s so the consumer
    can decide how to persist them (write to a specific directory, keep
    them in memory, etc.) — unlike `FileValueRenderer.render()` which eagerly
    materializes non-file streams into temporary files.
    """
    def __init__(
        self,
        source: Union[List[StreamResource], AsyncIterable[StreamResource]],
        is_single: bool = False,
    ):
        self.source: Union[List[StreamResource], AsyncIterable[StreamResource]] = source
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[StreamResource]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[StreamResource]:
        if isinstance(self.source, AsyncIterable):
            return [ item async for item in self.source ]

        return self.source

class FileValueRenderer:
    async def render_array(
        self,
        value: Any,
        single_as_array: bool = False,
    ) -> Optional[Union[FileArrayValue, List[Optional[FileArrayValue]], AsyncIterator[Optional[FileArrayValue]]]]:
        # Fragmented streams represent one logical file array delivered in
        # pieces — fall through to `_render_element_array` which wraps them
        # into a single streaming FileArrayValue.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element_array(chunk, single_as_array)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, StreamChunkIterator)):
            return [ await self._render_element_array(item, single_as_array) for item in value ]

        return await self._render_element_array(value, single_as_array)

    async def render(
        self,
        value: Any
    ) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element_array(self, value: Any, single_as_array: bool = False) -> Optional[FileArrayValue]:
        if isinstance(value, FileArrayValue):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    if isinstance(item, StreamResource):
                        yield item
            return FileArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return FileArrayValue([ item for item in value if isinstance(item, StreamResource) ])

        if single_as_array and isinstance(value, StreamResource):
            return FileArrayValue([ value ], is_single=True)

        return None

    async def _render_element(self, value: Any) -> Optional[str]:
        if isinstance(value, FileStreamResource):
            return os.path.expanduser(value.path)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, None)

        return None
