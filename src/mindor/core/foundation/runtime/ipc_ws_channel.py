from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional
from mindor.core.foundation.runtime.ipc_message import IpcMessage, IpcMessageType
from mindor.core.foundation.runtime.ipc_worker import IpcRuntimeWorker
from mindor.core.logger import logging
import asyncio

# Factory that builds the worker after the START handshake on a WS channel.
# Receives the START message and the server-side WebSocket connection; returns
# anything with an async `run()`.
IpcWsWorkerFactory = Callable[[IpcMessage, Any], IpcRuntimeWorker]

# Cloudflare's HTTP proxy drops idle connections at ~100s. Send WS pings well
# below that window so the server-side proxy stays alive during model loads
# and other long gaps between IPC traffic.
_DEFAULT_PING_INTERVAL = 30.0

class IpcWsServerChannel:
    """Hosts a WebSocket server that drives an `IpcRuntimeWorker` over a single
    long-lived connection.

    The server is single-connection: once a client has handshaked successfully
    and started a session, further handshakes are rejected until the active
    session ends. The worker's own `run()` loop pumps the WS binary frames.

    Expected authorization:
    - the client sends `Authorization: Bearer <token>` on the WS upgrade;
    - the server rejects any upgrade whose token does not match
      ``auth_token`` (constant-time compare).
    """
    def __init__(
        self,
        worker_factory: IpcWsWorkerFactory,
        auth_token: str,
        host: str = "0.0.0.0",
        port: int = 8000,
        ping_interval: float = _DEFAULT_PING_INTERVAL,
    ) -> None:
        self.worker_factory: IpcWsWorkerFactory = worker_factory
        self.host: str = host
        self.port: int = port
        self.auth_token: str = auth_token
        self.ping_interval: float = ping_interval

        self._server = None
        self._session_lock = asyncio.Lock()

    async def serve(self) -> None:
        """Run the WS server until the worker's dispatch loop exits.

        Blocks the calling coroutine; typical use is as a Pod entrypoint's
        ``asyncio.run(channel.serve())``.
        """
        import websockets  # local import so the module is importable without the dep installed

        async def _handler(websocket) -> None:
            if not self._authorize(websocket):
                await websocket.close(code=4401, reason="unauthorized")
                return

            # Reject concurrent sessions — the worker owns the component
            # lifecycle and cannot be driven by two proxies at once.
            if self._session_lock.locked():
                await websocket.close(code=4409, reason="session already active")
                return

            async with self._session_lock:
                await self._run_session(websocket)

        self._server = await websockets.serve(
            _handler,
            self.host,
            self.port,
            ping_interval=self.ping_interval,
            # Keep max_size unbounded — IPC binary trailers can carry large
            # tensor chunks. Streaming codec splits them above the pipeline;
            # the WS frame itself should not impose an extra limit.
            max_size=None,
        )

        try:
            await self._server.wait_closed()
        finally:
            self._server = None

    def _authorize(self, websocket) -> bool:
        import hmac

        header = websocket.request.headers.get("Authorization", "")

        if not header.lower().startswith("bearer "):
            return False

        auth_token = header[len("bearer "):].strip()

        return hmac.compare_digest(auth_token, self.auth_token)

    async def _run_session(self, websocket) -> None:
        start_message = await self._recv_start(websocket)

        if start_message is None:
            return

        worker = self.worker_factory(start_message, websocket)
        await worker.run()

    @staticmethod
    async def _recv_start(websocket) -> Optional[IpcMessage]:
        import websockets.exceptions

        try:
            frame = await websocket.recv()
        except websockets.exceptions.ConnectionClosed:
            return None

        if isinstance(frame, str):
            logging.warning("ipc-ws: discarding text frame; expected START binary frame")
            return None

        message = IpcMessage.deserialize(frame)

        if message.type != IpcMessageType.START:
            logging.warning("ipc-ws: expected START as first frame, got %r", message.type)
            return None

        return message

class IpcWsClientTransport:
    """Thin async wrapper over a `websockets` client connection.

    Mixed into an `IpcRuntimeProxy` subclass as the transport layer: each WS
    binary frame carries exactly one serialized `IpcMessage`.
    """
    def __init__(
        self,
        url: str,
        auth_token: str,
        ping_interval: float = _DEFAULT_PING_INTERVAL,
        connect_timeout: float = 60.0,
    ) -> None:
        self.url: str = url
        self.auth_token: str = auth_token
        self.ping_interval: float = ping_interval
        self.connect_timeout: float = connect_timeout

        self._websocket = None

    async def connect(self) -> None:
        import websockets

        self._websocket = await asyncio.wait_for(
            websockets.connect(
                self.url,
                additional_headers={ "Authorization": f"Bearer {self.auth_token}" },
                ping_interval=self.ping_interval,
                max_size=None,
            ),
            timeout=self.connect_timeout,
        )

    async def send(self, message: bytes) -> None:
        if self._websocket is None:
            raise ConnectionError("ipc-ws: send on closed transport")

        await self._websocket.send(message)

    async def recv(self) -> Optional[bytes]:
        import websockets.exceptions

        if self._websocket is None:
            return None

        try:
            frame = await self._websocket.recv()
        except websockets.exceptions.ConnectionClosed:
            return None

        if isinstance(frame, str):
            # Server shouldn't send text frames; treat as EOF for safety
            return None

        return frame

    async def close(self) -> None:
        if self._websocket is None:
            return

        try:
            await self._websocket.close()
        finally:
            self._websocket = None
