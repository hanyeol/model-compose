from __future__ import annotations

from typing import Optional, Tuple
from PIL import ImageFont

# Platform-specific system fonts that cover Chinese/Japanese/Korean glyphs.
# Tried in order when a caller needs CJK coverage but has no font path of its
# own; PIL's default bitmap font ships with ASCII only, so those glyphs would
# otherwise render as `.notdef` boxes.
_CJK_FONT_CANDIDATES: Tuple[str, ...] = (
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    # Linux (Noto CJK is the standard fallback shipped by most distros)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    # Windows
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/msgothic.ttc",
    "C:/Windows/Fonts/simsun.ttc",
)


def find_cjk_font(size: int = 16) -> Optional[ImageFont.FreeTypeFont]:
    """Try to load the first available CJK-capable system font.

    Returns the loaded `ImageFont.FreeTypeFont` when one of the platform
    candidates opens, or None when none of them are installed. Callers
    typically fall back to their default font (with a warning) on None.
    """
    for candidate in _CJK_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue

    return None
