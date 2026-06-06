from typing import Optional, Tuple, List, AsyncIterator
from pathlib import PurePosixPath
from tempfile import NamedTemporaryFile
import asyncio, mimetypes, os

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

def get_file_extension(path: Optional[str]) -> Optional[str]:
    if path:
        extension = os.path.splitext(path)[1].lstrip(".")
        return extension or None

    return None

def guess_content_type(path: Optional[str]) -> Optional[str]:
    if path:
        content_type, _ = mimetypes.guess_type(path)
        return content_type

    return None

def create_temporary_file(extension: Optional[str] = None) -> str:
    file = NamedTemporaryFile(suffix=f".{extension}" if extension else None, delete=False)
    path = file.name
    file.close()

    return path
