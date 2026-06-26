from typing import Any, Optional
from collections.abc import AsyncIterator, AsyncIterable
from abc import ABC, abstractmethod
from enum import Enum
import json

class EventStreamFormat(str, Enum):
    TEXT = "text"
    JSON = "json"

class StreamIterator(ABC):
    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iterate_stream()

    @abstractmethod
    async def _iterate_stream(self) -> AsyncIterator[Any]:
        pass

class StreamChunkIterator(StreamIterator):
    def __init__(self, source: AsyncIterable):
        self.source: AsyncIterable = source

    async def _iterate_stream(self) -> AsyncIterator[Any]:
        async for chunk in self.source:
            if chunk is not None:
                yield chunk

class EventStreamIterator(StreamIterator):
    def __init__(
        self,
        source: AsyncIterable,
        format: Optional[EventStreamFormat] = None
    ):
        self.source: AsyncIterable = source
        self.format: Optional[EventStreamFormat] = format

    async def _iterate_stream(self) -> AsyncIterator[Any]:
        async for chunk in self.source:
            if chunk is None:
                continue

            encoded = self._encode_chunk(chunk)

            if encoded is None:
                continue

            yield encoded

    def _encode_chunk(self, chunk: Any) -> Optional[Any]:
        if self.format == EventStreamFormat.TEXT:
            return chunk if isinstance(chunk, str) else str(chunk)

        if self.format == EventStreamFormat.JSON:
            return json.dumps(chunk, ensure_ascii=False, default=str)

        if not isinstance(chunk, (str, bytes, type(None))):
            return json.dumps(chunk, ensure_ascii=False, default=str)

        return chunk
