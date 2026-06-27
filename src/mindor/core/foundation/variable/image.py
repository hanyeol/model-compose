from typing import List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource
from ..streaming.image import load_image_from_stream, ImageStreamResource
from PIL import Image as PILImage

class ImageValueRenderer:
    async def render_array(self, value: Any) -> Union[List[PILImage.Image], List[List[PILImage.Image]], AsyncIterator[List[PILImage.Image]]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for array in value:
                    yield await self._render_element_array(array)
            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
            return [ await self._render_element_array(array) for array in value ]

        return await self._render_element_array(value)

    async def render(self, value: Any) -> Union[PILImage.Image, List[PILImage.Image], AsyncIterator[PILImage.Image]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for element in value:
                    yield await self._render_element(element)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element_array(self, value: Any) -> List[PILImage.Image]:
        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        raise TypeError(f"Cannot render element of type {type(value).__name__} as list of images")

    async def _render_element(self, value: Any) -> PILImage.Image:
        if isinstance(value, PILImage.Image):
            return value

        if isinstance(value, ImageStreamResource):
            return value.image

        if isinstance(value, StreamResource):
            return await load_image_from_stream(value)

        raise TypeError(f"Cannot render element of type {type(value).__name__} as image")
