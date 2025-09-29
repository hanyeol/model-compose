from typing import Optional, Dict, Any
from websockets.asyncio.client import ClientConnection
import websockets, asyncio, json

class WebSocketClient:
    def __init__(
        self,
        url: str,
        ping_interval: Optional[float] = None,
        ping_timeout: Optional[float] = None,
        receive_timeout: Optional[float] = None
    ):
        self.url: str = url
        self.ping_interval: Optional[float] = ping_interval
        self.ping_timeout: Optional[float] = ping_timeout
        self.receive_timeout: Optional[float] = receive_timeout
        self.websocket: Optional[ClientConnection] = None

        self._connected: bool = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self) -> None:
        self.websocket = await websockets.connect(
            self.url,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout
        )

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def send_message(self, message: Dict[str, Any]) -> None:
        await self.websocket.send(json.dumps(message))

    async def receive_message(self) -> Dict[str, Any]:
        if self.receive_timeout:
            message = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=self.receive_timeout
            )
        else:
            message = await self.websocket.recv()

        return json.loads(message)

    @property
    def connected(self) -> bool:
        return bool(self.websocket)
