from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Callable, List, Optional
from types import FrameType
import contextlib
import threading

if TYPE_CHECKING:
    import uvicorn

_servers: List[uvicorn.Server] = []
_servers_lock = threading.Lock()
_shutdown_signal_handlers: dict = {}

# When multiple uvicorn servers coexist (controller adapter + listeners +
# webui), uvicorn.Server.capture_signals overwrites the previous server's
# handler via signal.signal, so only the last-registered server would react
# to SIGINT/SIGTERM. We replace capture_signals with a registry-based
# handler: every live UvicornServer is dispatched to on signal receipt.
#
# uvicorn.Server.capture_signals also re-raises every captured signal when
# its context exits, which for SIGTERM triggers the default handler
# (process death) inside serve() and skips owning cleanup. We skip that
# re-raise — ownership of the final exit status belongs to the caller
# (controller launch path), which re-raises after cleanup to preserve
# -SIGTERM exit codes.
#
# The subclass is defined inside create_uvicorn_server so importing this
# module does not pull uvicorn (and its transitive deps) into memory on
# CLI startup.
def create_uvicorn_server(
    *args: Any,
    on_shutdown_signal: Optional[Callable[[int], None]] = None,
    **kwargs: Any,
) -> uvicorn.Server:
    import uvicorn

    class UvicornServer(uvicorn.Server):
        @contextlib.contextmanager
        def capture_signals(self):
            if threading.current_thread() is not threading.main_thread():
                yield
                return

            with _servers_lock:
                if not _servers:
                    _install_shutdown_signal_handlers()

                _servers.append(self)

            try:
                yield
            finally:
                with _servers_lock:
                    _servers.remove(self)

                    if not _servers:
                        _uninstall_shutdown_signal_handlers()

        def handle_exit(self, sig: int, frame: Optional[FrameType]) -> None:
            super().handle_exit(sig, frame)

            if on_shutdown_signal is not None:
                on_shutdown_signal(sig)

    return UvicornServer(uvicorn.Config(*args, **kwargs))

def _install_shutdown_signal_handlers() -> None:
    import signal

    for sig in (signal.SIGINT, signal.SIGTERM):
        _shutdown_signal_handlers[sig] = signal.signal(sig, _dispatch_shutdown_signal)

def _uninstall_shutdown_signal_handlers() -> None:
    import signal

    for sig, handler in _shutdown_signal_handlers.items():
        signal.signal(sig, handler)

    _shutdown_signal_handlers.clear()

def _dispatch_shutdown_signal(sig: int, frame: Optional[FrameType]) -> None:
    with _servers_lock:
        targets = list(_servers)

    for server in targets:
        server.handle_exit(sig, frame)
