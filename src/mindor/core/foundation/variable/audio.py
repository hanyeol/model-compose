from typing import List, Literal, Optional, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.audio import create_audio_source, AudioBufferStreamer, PcmStreamResource
from ...utils.audio import AudioBuffer
from ..streaming.media import MediaSource
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class AudioBufferArrayValue:
    """A materialized or streaming array of audio buffers.

    Backed by either a `List[AudioBuffer]` (re-iterable) or an
    `AsyncIterable[AudioBuffer]` (one-shot). Consumers use `async for` to
    iterate lazily, or `await collect()` when the full list is needed.
    """
    def __init__(self, source: Union[List[AudioBuffer], AsyncIterable[AudioBuffer]]):
        self.source: Union[List[AudioBuffer], AsyncIterable[AudioBuffer]] = source

    def __aiter__(self) -> AsyncIterator[AudioBuffer]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()
        return self.source.__aiter__()

    async def collect(self) -> List[AudioBuffer]:
        if isinstance(self.source, list):
            return self.source
        return [ item async for item in self.source ]

class AudioValueRenderer:
    async def render(self, value: Any) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
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

    async def _render_element(self, value: Any) -> Optional[MediaSource]:
        if value is not None:
            return create_audio_source(value)

        return None

class AudioBufferValueRenderer:
    def __init__(self, sample_rate: Optional[int] = None, channel: Optional[Union[int, Literal["mono"]]] = None):
        self.sample_rate = sample_rate
        self.channel = channel

    async def render_array(
        self,
        value: Any
    ) -> Optional[Union[AudioBufferArrayValue, List[Optional[AudioBufferArrayValue]], AsyncIterator[Optional[AudioBufferArrayValue]]]]:
        # Fragmented streams represent a single logical audio buffer array
        # delivered in pieces — fall through to `_render_element_array` which
        # wraps them into one streaming AudioBufferArrayValue.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element_array(chunk)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, StreamChunkIterator)):
            return [ await self._render_element_array(item) for item in value ]

        return await self._render_element_array(value)

    async def render(
        self,
        value: Any
    ) -> Optional[Union[AudioBuffer, List[Optional[AudioBuffer]], AsyncIterator[Optional[AudioBuffer]]]]:
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

    async def _render_element_array(self, value: Any) -> Optional[AudioBufferArrayValue]:
        if isinstance(value, AudioBufferArrayValue):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    buffer = await self._render_element(item)
                    if buffer is not None:
                        yield buffer
            return AudioBufferArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return AudioBufferArrayValue([ await self._render_element(item) for item in value ])

        return None

    async def _render_element(self, value: Any) -> Optional[AudioBuffer]:
        if isinstance(value, PcmStreamResource) and isinstance(value.samples, AudioBuffer):
            if value.samples.matches(self.sample_rate, self.channel):
                return value.samples # AudioBuffer

        if isinstance(value, AudioBuffer):
            if value.matches(self.sample_rate, self.channel):
                return value
            value = PcmStreamResource(value)

        if value is not None:
            return await AudioBufferStreamer(
                create_audio_source(value),
                sample_rate=self.sample_rate,
                channel=self.channel
            ).collect()

        return None
