from __future__ import annotations

from typing import Optional
import shutil

def resolve_ffmpeg_executable() -> Optional[str]:
    """Locate an ffmpeg executable.

    Preference order:
      1. `ffmpeg` on PATH (system install)
      2. imageio-ffmpeg's bundled binary (pip wheel), if the package is installed

    Returns the resolved absolute path, or None if neither is available.
    """
    path = shutil.which("ffmpeg")

    if path is not None:
        return path

    try:
        import imageio_ffmpeg
    except ImportError:
        return None

    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (RuntimeError, OSError):
        return None

def resolve_ffprobe_executable() -> Optional[str]:
    """Locate an ffprobe executable.

    Only checks PATH — imageio-ffmpeg does not bundle ffprobe. Users who need
    ffprobe without a system install should `pip install static-ffmpeg` or
    similar and ensure the binary is on PATH.
    """
    return shutil.which("ffprobe")

def is_ffmpeg_available() -> bool:
    """Return True if an ffmpeg executable can be resolved."""
    return resolve_ffmpeg_executable() is not None

def is_ffprobe_available() -> bool:
    """Return True if an ffprobe executable can be resolved."""
    return resolve_ffprobe_executable() is not None
