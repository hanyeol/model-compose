from typing import Optional
from .streaming import StreamResource
from PIL import Image as PILImage
import io, base64

async def load_image_from_stream(stream: StreamResource, extension: Optional[str]) -> Optional[PILImage.Image]:
    try:
        data = bytearray()
        async with stream:
            async for chunk in stream:
                data.extend(chunk)
            return PILImage.open(io.BytesIO(data))
    except Exception as e:
        return None
