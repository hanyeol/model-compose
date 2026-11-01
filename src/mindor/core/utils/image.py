from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional
import io

if TYPE_CHECKING:
    from PIL import Image as PILImage

def convert(
    image: PILImage.Image,
    width: int,
    height: int,
    mode: str = "RGB",
    resample: Optional[int] = None,
) -> PILImage.Image:
    """Return `image` in the given color mode, resized to (width, height) if needed."""
    from PIL import Image as PILImage

    image = image.convert(mode)

    if image.size != (width, height):
        image = image.resize((width, height), resample if resample is not None else PILImage.LANCZOS)

    return image

def compose_with_alpha(image: PILImage.Image, alpha: PILImage.Image) -> PILImage.Image:
    from PIL import Image as PILImage

    if alpha.size != image.size:
        alpha = alpha.resize(image.size, PILImage.Resampling.LANCZOS)

    image = image.convert("RGBA")
    image.putalpha(alpha)

    return image

def probe_format(data: bytes) -> Optional[str]:
    from PIL import Image as PILImage

    try:
        with PILImage.open(io.BytesIO(data)) as image:
            return image.format.lower() if image.format else None
    except (PILImage.UnidentifiedImageError, OSError):
        return None

def has_alpha(image: PILImage.Image) -> bool:
    if image.mode in ("RGBA", "LA"):
        return True

    if image.mode == "P" and "transparency" in image.info:
        return True

    return False
