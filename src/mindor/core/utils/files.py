from typing import Optional, Tuple, List, Dict, AsyncIterator
from pathlib import PurePosixPath
from tempfile import NamedTemporaryFile
import aiofiles
import asyncio, mimetypes, os

_CONTENT_TYPE_EXTENSION_MAP: Dict[str, str] = {
    "audio/wav":        "wav",
    "audio/x-wav":      "wav",
    "audio/mpeg":       "mp3",
    "audio/mp3":        "mp3",
    "audio/aac":        "aac",
    "audio/mp4":        "m4a",
    "audio/flac":       "flac",
    "audio/ogg":        "ogg",
    "audio/opus":       "opus",
    "audio/webm":       "webm",
    "video/mp4":        "mp4",
    "video/quicktime":  "mov",
    "video/webm":       "webm",
    "video/x-matroska": "mkv",
    "video/x-msvideo":  "avi",
    "video/x-flv":      "flv",
    "video/x-ms-wmv":   "wmv",
    "video/mpeg":       "mpeg",
    "video/mp2t":       "ts",
    "video/3gpp":       "3gp",
    "video/ogg":        "ogv",
    "image/png":        "png",
    "image/jpeg":       "jpg",
    "image/webp":       "webp",
    "image/bmp":        "bmp",
    "image/gif":        "gif",
    "image/tiff":       "tiff",
    "image/x-icon":     "ico",
}

async def list_dir(path: str) -> Tuple[List[str], List[Tuple[str, os.stat_result]]]:
    def _scan_dir() -> Tuple[List[str], List[Tuple[str, os.stat_result]]]:
        dirnames: List[str] = []
        files: List[Tuple[str, os.stat_result]] = []
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    dirnames.append(entry.name)
                elif entry.is_file(follow_symlinks=False):
                    files.append((entry.name, entry.stat(follow_symlinks=False)))
        return dirnames, files

    return await asyncio.to_thread(_scan_dir)

async def walk_dir(path: str) -> AsyncIterator[Tuple[str, List[str], List[Tuple[str, os.stat_result]]]]:
    pending: List[str] = [ path ]
    while pending:
        current = pending.pop(0)
        try:
            dirnames, files = await list_dir(current)
        except (FileNotFoundError, PermissionError):
            continue
        yield current, dirnames, files
        for name in dirnames:
            pending.append(os.path.join(current, name))

async def save_string_to_temporary_file(content: str, extension: Optional[str] = None, encoding: str = "utf-8") -> str:
    path = get_temporary_path(extension)

    async with aiofiles.open(path, "w", encoding=encoding) as f:
        await f.write(content)

    return path

def get_temporary_path(
    extension: Optional[str] = None,
    dir: Optional[str] = None,
    reserve_file: bool = False,
) -> str:
    file = NamedTemporaryFile(suffix=f".{extension}" if extension else None, dir=dir, delete=False)
    path = file.name
    file.close()

    if not reserve_file:
        os.remove(path)

    return path

def is_glob_match(path: str, pattern: str) -> bool:
    path = normalize_path(path)

    # Shell glob semantics: path and pattern must agree on absoluteness.
    if not path or path.startswith("/") != pattern.startswith("/"):
        return False

    # Shell glob semantics:
    # "*.png" matches only files directly under the current/root directory.
    # It should NOT match "images/a.png".
    bare_path, bare_pattern = path.lstrip("/"), pattern.lstrip("/")

    if "/" not in bare_pattern:
        return "/" not in bare_path and PurePosixPath(bare_path).match(bare_pattern)

    return PurePosixPath(path).match(pattern)

def normalize_path(path: str) -> str:
    if os.sep == "\\":
        path = path.replace("\\", "/")

    return path.rstrip("/") or "/" if path else ""

def is_path_within(base: str, path: str) -> bool:
    absolute_base = os.path.abspath(base)
    absolute_path = os.path.abspath(path)

    return absolute_path == absolute_base or absolute_path.startswith(absolute_base + os.sep)

def get_file_extension(path: str) -> Optional[str]:
    _, extension = os.path.splitext(path)

    if extension:
        extension = extension.lstrip(".")

    return extension or None

def guess_file_extension(content_type: str) -> Optional[str]:
    content_type = content_type.split(";", 1)[0].strip().lower()
    extension = _CONTENT_TYPE_EXTENSION_MAP.get(content_type)

    if not extension:
        extension = mimetypes.guess_extension(content_type)

        if extension:
            extension = extension.lstrip(".")

    return extension

def guess_content_type(path: str) -> Optional[str]:
    content_type, _ = mimetypes.guess_type(path)

    return content_type
