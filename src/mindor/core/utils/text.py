from __future__ import annotations

from typing import Optional


def contains_cjk_characters(text: Optional[str]) -> bool:
    """Return True when `text` has any character in the main CJK Unicode blocks.

    Covers CJK Unified Ideographs, Hangul syllables, Hiragana, Katakana, and
    the common extensions. Doesn't try to be exhaustive — the goal is to
    catch the case where an ASCII-only font (e.g. PIL's default) would drop
    glyphs and render them as `.notdef` boxes.
    """
    if not text:
        return False

    for ch in text:
        code = ord(ch)
        if (
            0x3040 <= code <= 0x30FF or  # Hiragana + Katakana
            0x3400 <= code <= 0x4DBF or  # CJK Extension A
            0x4E00 <= code <= 0x9FFF or  # CJK Unified Ideographs
            0xAC00 <= code <= 0xD7A3 or  # Hangul syllables
            0xF900 <= code <= 0xFAFF     # CJK Compatibility Ideographs
        ):
            return True

    return False
