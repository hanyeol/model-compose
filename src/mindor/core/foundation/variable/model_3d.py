from typing import List, Optional, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.model_3d import create_model_3d_source
from ..streaming.media import MediaSource
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class Model3DArrayValue:
    """A materialized or streaming array of 3D model sources.

    Backed by either a `List[MediaSource]` (re-iterable) or an
    `AsyncIterable[MediaSource]` (one-shot). Consumers use `async for` to
    iterate lazily, or `await collect()` when the full list is needed.
    """
    def __init__(self, source: Union[List[MediaSource], AsyncIterable[MediaSource]], is_single: bool = False):
        self.source: Union[List[MediaSource], AsyncIterable[MediaSource]] = source
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[MediaSource]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[MediaSource]:
        if isinstance(self.source, AsyncIterable):
            return [ item async for item in self.source ]

        return self.source

class Model3DValueRenderer:
    async def render_array(
        self,
        value: Any,
        single_as_array: bool = False,
    ) -> Optional[Union[Model3DArrayValue, List[Optional[Model3DArrayValue]], AsyncIterator[Optional[Model3DArrayValue]]]]:
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element_array(chunk, single_as_array)

            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, StreamChunkIterator)):
            return [ await self._render_element_array(item, single_as_array) for item in value ]

        return await self._render_element_array(value, single_as_array)

    async def render(
        self,
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)

            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element_array(self, value: Any, single_as_array: bool = False) -> Optional[Model3DArrayValue]:
        if isinstance(value, Model3DArrayValue):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    model = await self._render_element(item)
                    if model is not None:
                        yield model
            return Model3DArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return Model3DArrayValue([ await self._render_element(item) for item in value ])

        if single_as_array:
            model = await self._render_element(value)
            if model is not None:
                return Model3DArrayValue([ model ], is_single=True)

        return None

    async def _render_element(self, value: Any) -> Optional[MediaSource]:
        if value is not None:
            return create_model_3d_source(value)

        return None
