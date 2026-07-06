from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource
from ..streaming.image import load_image_from_stream, ImageStreamResource
from ..streaming.iterators import StreamIterator
from PIL import Image as PILImage

class ImageValueRenderer:
    async def render_array(self, value: Any) -> Optional[Union[List[List[PILImage.Image]], AsyncIterator[List[PILImage.Image]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element_array(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
            return [ await self._render_element_array(item) for item in value ]

        return [ await self._render_element_array(value) ]

    async def render(self, value: Any) -> Optional[Union[PILImage.Image, List[PILImage.Image], AsyncIterator[PILImage.Image]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element_array(self, value: Any) -> Optional[List[PILImage.Image]]:
        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return None

    async def _render_element(self, value: Any) -> Optional[PILImage.Image]:
        if isinstance(value, PILImage.Image):
            return value

        if isinstance(value, ImageStreamResource):
            return value.image

        if isinstance(value, StreamResource):
            return await load_image_from_stream(value)

        return None
