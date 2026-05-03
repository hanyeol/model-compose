from typing import Optional, Union, Dict, Any, Tuple
from collections.abc import AsyncIterator
from websockets.asyncio.client import ClientConnection
from urllib.parse import urlencode
import websockets, asyncio, json

class WebSocketConnection:
    def __init__(self, websocket: ClientConnection, receive_timeout: Optional[float] = None):
        self.websocket: ClientConnection = websocket
        self.receive_timeout: Optional[float] = receive_timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def send_message(self, message: Any) -> None:
        await self.websocket.send(json.dumps(message))

    async def send_bytes(self, data: bytes) -> None:
        await self.websocket.send(data)

    async def receive_message(self) -> Dict[str, Any]:
        if self.receive_timeout:
            message = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=self.receive_timeout
            )
        else:
            message = await self.websocket.recv()

        return json.loads(message)

    async def receive_frame(self) -> Union[str, bytes]:
        if self.receive_timeout:
            return await asyncio.wait_for(
                self.websocket.recv(),
                timeout=self.receive_timeout
            )
        return await self.websocket.recv()

    async def receive_frames(self) -> AsyncIterator[Union[str, bytes]]:
        try:
            while True:
                yield await self.receive_frame()
        except (websockets.ConnectionClosed, websockets.ConnectionClosedOK):
            return
        except asyncio.TimeoutError:
            return

    def is_connected(self) -> bool:
        return bool(self.websocket)

class WebSocketClient:
    def __init__(
        self,
        base_url: str,
        ping_interval: Optional[float] = None,
        ping_timeout: Optional[float] = None,
        additional_headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None
    ):
        self.base_url: str = base_url
        self.ping_interval: Optional[float] = ping_interval
        self.ping_timeout: Optional[float] = ping_timeout
        self.additional_headers: Optional[Dict[str, str]] = additional_headers
        self._params: Optional[Dict[str, Any]] = params
        self._connection: Optional[WebSocketConnection] = None

    async def connect(
        self,
        path: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        receive_timeout: Optional[float] = None
    ) -> Tuple[WebSocketConnection, bool]:
        if path or params or headers:  # new owned connection per request
            connection = await self._connect(
                path=path,
                params={ **(self._params or {}), **(params or {}) } or None,
                headers=headers,
                receive_timeout=receive_timeout
            )
            return connection, True
        if not self._connection or not self._connection.is_connected():
            self._connection = await self._connect()
        return self._connection, False

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _connect(
        self,
        path: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        receive_timeout: Optional[float] = None
    ) -> WebSocketConnection:
        url = self.base_url
        if path:
            url += path if path.startswith("/") else f"/{path}"
        if params:
            filtered = { k: v for k, v in params.items() if v is not None }
            if filtered:
                url += "?" + urlencode(filtered)

        ws = await websockets.connect(
            url,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
            additional_headers={ **(self.additional_headers or {}), **(headers or {}) } or None
        )

        return WebSocketConnection(ws, receive_timeout)
