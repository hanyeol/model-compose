from typing import Optional
from io import TextIOWrapper
import anyio, os, sys

class StdoutRelay:
    """Reserve process stdout (fd 1) for a caller and relay stray writes to stderr.

    On enter: dups fd 1 to keep the original stdout, points fd 1 at fd 2 so any
    incidental output (print, logging default handlers, third-party libs) flows
    to stderr, and swaps sys.stdout to sys.stderr. Yields an anyio-wrapped
    binary stream that writes to the original stdout — used by stdio-framed
    protocols (e.g. MCP) that need an uncontaminated stdout channel.

    On exit: restores sys.stdout. fd 1 remains pointed at stderr; callers
    typically use this at process end-of-life.
    """
    def __init__(self) -> None:
        self._original_stdout_fd: Optional[int] = None
        self._saved_sys_stdout = None

    def __enter__(self) -> anyio.AsyncFile:
        self._original_stdout_fd = os.dup(1)
        os.dup2(2, 1)

        self._saved_sys_stdout = sys.stdout
        sys.stdout = sys.stderr

        return anyio.wrap_file(TextIOWrapper(
            os.fdopen(self._original_stdout_fd, "wb", buffering=0),
            encoding="utf-8",
        ))

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._saved_sys_stdout is not None:
            sys.stdout = self._saved_sys_stdout
            self._saved_sys_stdout = None
