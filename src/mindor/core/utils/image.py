from typing import Optional
from PIL import Image as PILImage
import io

def convert(
    image: PILImage.Image,
    width: int,
    height: int,
    mode: str = "RGB",
    resample: int = PILImage.LANCZOS,
) -> PILImage.Image:
    """Return `image` in the given color mode, resized to (width, height) if needed."""
    image = image.convert(mode)

    if image.size != (width, height):
        image = image.resize((width, height), resample)

    return image

def compose_with_alpha(image: PILImage.Image, alpha: PILImage.Image) -> PILImage.Image:
    if alpha.size != image.size:
        alpha = alpha.resize(image.size, PILImage.Resampling.LANCZOS)

    image = image.convert("RGBA")
    image.putalpha(alpha)

    return image

def has_alpha(image: PILImage.Image) -> bool:
    return image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)

def probe_format(data: bytes) -> Optional[str]:
    try:
        with PILImage.open(io.BytesIO(data)) as image:
            return image.format.lower() if image.format else None
    except (PILImage.UnidentifiedImageError, OSError):
        return None
