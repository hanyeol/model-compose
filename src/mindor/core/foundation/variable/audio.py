from typing import List, Literal, Optional, TypeAlias, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.audio import create_audio_source, AudioBufferStreamer, AudioBufferStreamIterator, PcmStreamResource
from ...utils.audio import AudioBuffer
from ..streaming.media import MediaSource
from ..streaming.iterators import StreamIterator, StreamChunkIterator

# A single audio, either materialized or streaming.
AudioBufferValue: TypeAlias = Union[AudioBuffer, AudioBufferStreamIterator]

class AudioArrayValue:
    """A materialized or streaming array of audio sources.

    Backed by either a `List[MediaSource]` (re-iterable) or an
    `AsyncIterable[MediaSource]` (one-shot). Consumers use `async for` to
    iterate lazily, or `await collect()` when the full list is needed.
    """
    def __init__(self, source: Union[List[MediaSource], AsyncIterable[MediaSource]]):
        self.source: Union[List[MediaSource], AsyncIterable[MediaSource]] = source

    def __aiter__(self) -> AsyncIterator[MediaSource]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[MediaSource]:
        if isinstance(self.source, list):
            return self.source

        return [ item async for item in self.source ]

class AudioBufferArrayValue:
    """A materialized or streaming array of audio buffers.

    Backed by either a ``List[AudioBufferValue]``
    (re-iterable) or an ``AsyncIterable[AudioBufferValue]``
    (one-shot). Consumers use ``async for`` to iterate lazily, or ``await collect()``
    when the full list of ``AudioBuffer`` values is needed — streaming iterators in
    the source are collected on demand.
    """
    def __init__(self, source: Union[List[AudioBufferValue], AsyncIterable[AudioBufferValue]]):
        self.source: Union[List[AudioBufferValue], AsyncIterable[AudioBufferValue]] = source

    def __aiter__(self) -> AsyncIterator[AudioBufferValue]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item

            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[AudioBuffer]:
        items = self.source if isinstance(self.source, list) else [ item async for item in self.source ]

        audios: List[AudioBuffer] = []
        for item in items:
            if isinstance(item, AudioBufferStreamIterator):
                item = await item.collect()
            audios.append(item)

        return audios

class AudioValueRenderer:
    async def render_array(
        self,
        value: Any
    ) -> Optional[Union[AudioArrayValue, List[Optional[AudioArrayValue]], AsyncIterator[Optional[AudioArrayValue]]]]:
        # Fragmented streams represent a single logical audio array delivered
        # in pieces — fall through to `_render_element_array` which wraps them
        # into one streaming AudioArrayValue.
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
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
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

    async def _render_element_array(self, value: Any) -> Optional[AudioArrayValue]:
        if isinstance(value, AudioArrayValue):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    audio = await self._render_element(item)
                    if audio is not None:
                        yield audio
            return AudioArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return AudioArrayValue([ await self._render_element(item) for item in value if item is not None ])

        return None

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
        value: Any,
        collect: bool = True,
    ) -> Optional[Union[AudioBufferArrayValue, List[Optional[AudioBufferArrayValue]], AsyncIterator[Optional[AudioBufferArrayValue]]]]:
        # Fragmented streams represent a single logical audio buffer array
        # delivered in pieces — fall through to `_render_element_array` which
        # wraps them into one streaming AudioBufferArrayValue.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element_array(chunk, collect=collect)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, StreamChunkIterator)):
            return [ await self._render_element_array(item, collect=collect) for item in value ]

        return await self._render_element_array(value, collect=collect)

    async def render(
        self,
        value: Any,
        collect: bool = True,
    ) -> Optional[Union[AudioBufferValue, List[Optional[AudioBufferValue]], AsyncIterator[Optional[AudioBufferValue]]]]:
        # Fragmented streams represent a single logical audio buffer delivered
        # in pieces — fall through to ``_render_element`` so ``collect`` decides
        # whether to materialize into one AudioBuffer or pass the stream through.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk, collect=collect)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item, collect=collect) for item in value ]

        return await self._render_element(value, collect=collect)

    async def _render_element_array(self, value: Any, collect: bool = True) -> Optional[AudioBufferArrayValue]:
        if isinstance(value, AudioBufferArrayValue):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    rendered = await self._render_element(item, collect=collect)
                    if rendered is not None:
                        yield rendered
            return AudioBufferArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return AudioBufferArrayValue([ await self._render_element(item, collect=collect) for item in value ])

        return None

    async def _render_element(self, value: Any, collect: bool = True) -> Optional[AudioBufferValue]:
        if isinstance(value, PcmStreamResource) and isinstance(value.samples, AudioBufferStreamIterator):
            value = value.samples

        if isinstance(value, AudioBufferStreamIterator):
            if value.matches(self.sample_rate, self.channel):
                return (await value.collect()) if collect else value
            value = PcmStreamResource(value)

        if isinstance(value, AudioBuffer):
            if value.matches(self.sample_rate, self.channel):
                return value if collect else AudioBufferStreamIterator.from_single(value)
            value = PcmStreamResource(AudioBufferStreamIterator.from_single(value))

        if value is not None:
            streamer = AudioBufferStreamer(
                create_audio_source(value),
                sample_rate=self.sample_rate,
                channel=self.channel,
            )
            return (await streamer.collect()) if collect else (await streamer.as_iterator())

        return None
