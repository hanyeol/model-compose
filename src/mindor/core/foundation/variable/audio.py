from typing import List, Optional, Union, Any
from collections.abc import AsyncIterator
from ..streaming.audio import create_audio_source, load_audio_buffer
from ...utils.audio import AudioBuffer
from ..streaming.media import MediaSource
from ..streaming.iterators import StreamIterator

class AudioBufferArrayValue:
    def __init__(self, values: List[AudioBuffer]):
        self.values: List[AudioBuffer] = values

class AudioValueRenderer:
    async def render(self, value: Any) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element(self, value: Any) -> Optional[MediaSource]:
        if value is not None:
            return create_audio_source(value)

        return None

class AudioBufferValueRenderer:
    def __init__(self, sample_rate: Optional[int] = None, channel: Optional[int] = None):
        self.sample_rate = sample_rate
        self.channel = channel

    async def render_array(self, value: Any) -> Optional[Union[AudioBufferArrayValue, List[AudioBufferArrayValue], AsyncIterator[AudioBufferArrayValue]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element_array(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
            return [ await self._render_element_array(item) for item in value ]

        return await self._render_element_array(value)

    async def render(self, value: Any) -> Optional[Union[AudioBuffer, List[AudioBuffer], AsyncIterator[AudioBuffer]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element_array(self, value: Any) -> Optional[AudioBufferArrayValue]:
        if isinstance(value, AudioBufferArrayValue):
            return value

        if isinstance(value, (list, tuple)):
            return AudioBufferArrayValue([ await self._render_element(item) for item in value ])

        return None

    async def _render_element(self, value: Any) -> Optional[AudioBuffer]:
        if isinstance(value, AudioBuffer):
            return value

        if value is not None:
            source = create_audio_source(value)
            sample_rate, channel = self.sample_rate, self.channel

            return await load_audio_buffer(source, sample_rate, channel)

        return None
