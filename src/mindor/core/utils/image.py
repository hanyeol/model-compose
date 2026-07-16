from PIL import Image as PILImage

def compose_with_alpha(image: PILImage.Image, alpha: PILImage.Image) -> PILImage.Image:
    if alpha.size != image.size:
        alpha = alpha.resize(image.size, PILImage.Resampling.LANCZOS)

    image = image.convert("RGBA")
    image.putalpha(alpha)

    return image

def has_alpha(image: PILImage.Image) -> bool:
    return image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
