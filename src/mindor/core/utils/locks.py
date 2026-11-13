from __future__ import annotations

from typing import Optional
from pathlib import Path
import asyncio
import os
import time

class FileLock:
    """Lightweight cross-platform exclusive file lock context manager."""
    def __init__(self, path: Path):
        self.path = path
        self._fp = None

    def __enter__(self) -> FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self.path, "w")

        if os.name == "nt":  # Windows
            import msvcrt

            while True:
                try:
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.1)
        else:
            import fcntl

            fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX)

        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if os.name == "nt":
                import msvcrt

                try:
                    self._fp.seek(0)
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            else:
                import fcntl

                fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
        finally:
            self._fp.close()

class AsyncFileLock:
    """Async-friendly wrapper around `FileLock`.

    Acquires and releases the underlying blocking lock on the default
    executor so the event loop stays responsive during contention. Use as
    `async with AsyncFileLock(path): ...` wherever async code needs the
    same cross-process exclusivity guarantees `FileLock` provides to sync
    callers.
    """
    def __init__(self, path: Path):
        self._lock = FileLock(path)

    async def __aenter__(self) -> AsyncFileLock:
        await asyncio.get_event_loop().run_in_executor(None, self._lock.__enter__)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await asyncio.get_event_loop().run_in_executor(None, self._lock.__exit__, exc_type, exc, tb)
