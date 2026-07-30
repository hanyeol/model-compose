from __future__ import annotations

import re

# ffmpeg-style specifiers accepted in `filename_format`:
#   %d       frame index (1-based)
#   %0Nd     zero-padded frame index of width N
#   %%       literal '%'
_SPEC_PATTERN = re.compile(r"%(0\d+)?d")
_ESCAPED_PERCENT = "\x00"

def format_filename(pattern: str, index: int) -> str:
    escaped = pattern.replace("%%", _ESCAPED_PERCENT)

    def _replace(match: re.Match) -> str:
        width = match.group(1)
        return f"{index:0{int(width)}d}" if width else str(index)

    rendered = _SPEC_PATTERN.sub(_replace, escaped)

    if "%" in rendered:
        raise ValueError(f"Unsupported specifier in filename_format: {pattern!r}")

    return rendered.replace(_ESCAPED_PERCENT, "%")
