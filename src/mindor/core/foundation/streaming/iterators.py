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

class StreamChunkIterator(StreamIterator):
    def __init__(self, source: AsyncIterable, is_fragmented: bool = False):
        self.source: AsyncIterable = source
        self.is_fragmented: bool = is_fragmented

    async def _iterate_stream(self) -> AsyncIterator[Any]:
        iterator = self.source.__aiter__()

        try:
            async for chunk in iterator:
                if chunk is None and self.is_fragmented:
                    continue
                yield chunk
        finally:
            await close_iterator(iterator)

class StreamEncodingIterator(StreamIterator):
    def __init__(
        self,
        source: AsyncIterable,
        format: Optional[StreamEncodingFormat] = None
    ):
        self.source: AsyncIterable = source
        self.format: Optional[StreamEncodingFormat] = format

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
            await close_iterator(iterator)

    async def _encode_chunk(self, chunk: Any) -> Optional[Any]:
        if self.format == StreamEncodingFormat.TEXT:
            return chunk if isinstance(chunk, str) else str(chunk)

        if self.format == StreamEncodingFormat.JSON:
            return await encode_value_to_json(chunk)

        if not isinstance(chunk, (str, bytes, type(None))):
            return await encode_value_to_json(chunk)

        return chunk

async def close_iterator(iterator: Any) -> None:
    """Close an iterator that an `async for` stopped reading early, which Python does not
    do by itself (PEP 533): the source it reads from (an HTTP response, a model still
    generating) is released now, not when the source ends. Best effort."""
    aclose = getattr(iterator, "aclose", None)

    if aclose is not None:
        try:
            await aclose()
        except Exception:
            pass
