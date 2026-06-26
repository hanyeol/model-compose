from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource
from ..streaming.image import load_image_from_stream, ImageStreamResource
from PIL import Image as PILImage

class ImageValueRenderer:
    async def render(self, value: Any) -> Optional[Union[PILImage.Image, AsyncIterator[PILImage.Image], List[Optional[PILImage.Image]]]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for element in value:
                    yield await self._render_element(element)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, element: Any) -> Optional[PILImage.Image]:
        if isinstance(element, PILImage.Image):
            return element

        if isinstance(element, ImageStreamResource):
            return element.image

        if isinstance(element, StreamResource):
            return await load_image_from_stream(element)

        return None
