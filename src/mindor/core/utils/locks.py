from typing import Optional
from pathlib import Path
import os
import time

class FileLock:
    """Lightweight cross-platform exclusive file lock context manager."""
    def __init__(self, path: Path):
        self.path = path
        self._fp = None

    def __enter__(self) -> "FileLock":
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
