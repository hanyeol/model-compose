from typing import Any, Optional
from collections.abc import AsyncIterator, AsyncIterable
from abc import ABC, abstractmethod
from enum import Enum
from .json import encode_value_to_json

class StreamEncodingFormat(str, Enum):
    TEXT = "text"
    JSON = "json"

class StreamIterator(ABC):
    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iterate_stream()

    @abstractmethod
    async def _iterate_stream(self) -> AsyncIterator[Any]:
        pass

    async def _close_stream(self, iterator: AsyncIterable) -> None:
        closer = getattr(iterator, "aclose", None)

        if closer is not None:
            try:
                await closer()
            except Exception:
                pass

class StreamChunkIterator(StreamIterator):
    def __init__(self, source: AsyncIterable, is_fragmented: bool = False, resource: Optional[Any] = None):
        self.source: AsyncIterable = source
        self.is_fragmented: bool = is_fragmented
        # What the source reads from, such as an HTTP response. It is closed with the
        # stream, read or not: an async generator whose body never started does not run
        # its `finally` on aclose, so a source cannot release what it was handed.
        self.resource: Optional[Any] = resource

    async def aclose(self) -> None:
        await self._close_stream(self.source)

        closer = getattr(self.resource, "aclose", None) or getattr(self.resource, "close", None)

        if closer is None:
            return

        try:
            await closer()
        except Exception:
            pass

    async def _iterate_stream(self) -> AsyncIterator[Any]:
        iterator = self.source.__aiter__()

        try:
            async for chunk in iterator:
                if chunk is None and self.is_fragmented:
                    continue

                yield chunk
        finally:
            await self._close_stream(iterator)

class StreamEncodingIterator(StreamIterator):
    def __init__(
        self,
        source: AsyncIterable,
        format: Optional[StreamEncodingFormat] = None
    ):
        self.source: AsyncIterable = source
        self.format: Optional[StreamEncodingFormat] = format

    async def aclose(self) -> None:
        await self._close_stream(self.source)

    async def _iterate_stream(self) -> AsyncIterator[Any]:
        iterator = self.source.__aiter__()

        try:
            async for chunk in iterator:
                if chunk is None or chunk == "":
                    continue

                encoded = await self._encode_chunk(chunk)

                if encoded is None:
                    continue

                yield encoded
        finally:
            await self._close_stream(iterator)

    async def _encode_chunk(self, chunk: Any) -> Optional[Any]:
        if self.format == StreamEncodingFormat.TEXT:
            return chunk if isinstance(chunk, str) else str(chunk)

        if self.format == StreamEncodingFormat.JSON:
            return await encode_value_to_json(chunk)

        if not isinstance(chunk, (str, bytes, type(None))):
            return await encode_value_to_json(chunk)

        return chunk
