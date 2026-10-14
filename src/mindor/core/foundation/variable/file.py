from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.resources import StreamResource, save_stream_to_temporary_file
from ..streaming.file import FileStreamResource
from ..streaming.bytes import BytesStreamResource
from ..streaming.text import TextStreamResource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
import os

FileValue = str

class FileArrayValue:
    """A materialized or streaming array of files.

    Each element is a filesystem path ``str`` — ``FileValueRenderer`` spools
    any non-file input to a temp file before populating this container.
    Iteration and ``collect()`` do not do any per-item conversion.
    """
    def __init__(
        self,
        source: Union[List[FileValue], AsyncIterable[FileValue]],
        is_single: bool = False,
    ):
        self.source: Union[List[FileValue], AsyncIterable[FileValue]] = source
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[FileValue]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[FileValue]:
        if isinstance(self.source, AsyncIterable):
            return [ item async for item in self.source ]

        return self.source

class FileValueRenderer:
    async def render_array(
        self,
        value: Any,
        item_is_list: bool = False,
        single_as_array: bool = False,
    ) -> Optional[Union[FileArrayValue, List[Optional[FileArrayValue]], AsyncIterator[Any]]]:
        """Render a file array (or a nested list of them, with ``item_is_list=True``).

        With ``item_is_list=False`` (default) each ``value`` element is a single
        file ref, and nested lists are interpreted as a batch of file arrays.
        With ``item_is_list=True`` each ``value`` element is itself a group of
        file refs; the batch axis is always an explicit Python list, with
        non-batch inputs collapsing to a one-element list.
        """
        # Fragmented streams represent one logical file array delivered in
        # pieces — fall through to `_render_element_array` which wraps them
        # into a single streaming FileArrayValue.
        if isinstance(value, (StreamIterator, AsyncIterator)) and not self._is_fragmented_stream(value):
            async def _iterate():
                async for chunk in value:
                    if item_is_list:
                        yield await self._render_element_array(chunk, single_as_array=True)
                    else:
                        yield await self._render_element_array(chunk, single_as_array)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if item_is_list:
            if self._is_nested_element_array(value):
                return [ await self._render_element_array(item, single_as_array=True) for item in value ]

            if single_as_array and value is not None:
                return [ await self._render_element_array(value, single_as_array=True) ]

            return None

        if self._is_nested_element_array(value):
            return [ await self._render_element_array(item, single_as_array) for item in value ]

        return await self._render_element_array(value, single_as_array)

    async def render(
        self,
        value: Any,
    ) -> Optional[Union[str, List[Any], AsyncIterator[Any]]]:
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

    async def _render_element_array(
        self,
        value: Any,
        single_as_array: bool = False,
    ) -> Optional[FileArrayValue]:
        if isinstance(value, FileArrayValue):
            # Re-coerce lazily to the requested element contract.
            async def _iterate():
                async for item in value:
                    file = await self._render_element(item)
                    if file is not None:
                        yield file
            return FileArrayValue(_iterate(), is_single=value.is_single)

        if self._is_fragmented_stream(value):
            async def _iterate():
                async for item in value:
                    file = await self._render_element(item)
                    if file is not None:
                        yield file
            return FileArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return FileArrayValue([ await self._render_element(item) for item in value ])

        if single_as_array and value is not None:
            file = await self._render_element(value)
            if file is not None:
                return FileArrayValue([ file ], is_single=True)

        if value is not None:
            raise TypeError(
                f"expected a file array (list, FileArrayValue, or fragmented stream) "
                f"but got a single file. Join a per-item stream with \"+\"."
            )

        return None

    async def _render_element(self, value: Any) -> Optional[str]:
        """Normalize a raw value to a filesystem path. ``FileStreamResource``
        inputs pass through as their original path; other ``StreamResource``,
        ``str``, and ``bytes``/``bytearray`` inputs are spooled to a temp
        file and the temp path is returned.
        """
        if isinstance(value, FileStreamResource):
            return os.path.expanduser(value.path)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, None)

        if isinstance(value, str):
            return await save_stream_to_temporary_file(TextStreamResource(value), None)

        if isinstance(value, (bytes, bytearray)):
            return await save_stream_to_temporary_file(BytesStreamResource(value), None)

        return None

    def _is_nested_element_array(self, value: Any) -> bool:
        """True when ``value`` is a list of element arrays — a top-level
        list whose first item is itself an element array or a fragmented
        stream.
        """
        return (
            isinstance(value, (list, tuple))
            and bool(value)
            and (self._is_element_array(value[0]) or self._is_fragmented_stream(value[0]))
        )

    def _is_element_array(self, value: Any) -> bool:
        """True when ``value`` is a batch of file refs — a list/tuple of
        refs or an already-materialized ``FileArrayValue``.
        """
        return isinstance(value, (list, tuple, FileArrayValue))

    def _is_fragmented_stream(self, value: Any) -> bool:
        """True when ``value`` is a fragmented ``StreamChunkIterator`` — one
        logical file array delivered in pieces.
        """
        return isinstance(value, StreamChunkIterator) and value.is_fragmented
