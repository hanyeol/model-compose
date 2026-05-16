from __future__ import annotations

from typing import Optional, Dict, List, Any, Callable
from .websocket_client import WebSocketClient, WebSocketConnection
import aiohttp, asyncio, itertools

class CdpClient:
    """
    Thin CDP (Chrome DevTools Protocol) client built on WebSocketClient.

    Lifecycle:
      - connect() opens the WebSocket to the CDP debugger URL.
      - send_command() sends a JSON-RPC-style CDP message and awaits
        the matching response, correlating by incrementing integer id.
      - Events are dispatched via a background reader task.
      - close() cancels the reader and closes the WebSocket.
    """

    def __init__(self, ws_url: str, timeout: float = 30.0):
        self.ws_url: str = ws_url
        self.timeout: float = timeout
        self._websocket: Optional[WebSocketConnection] = None
        self._id_counter = itertools.count(1)
        self._pending: Dict[int, asyncio.Future] = {}
        self._event_listeners: Dict[str, List[Callable]] = {}
        self._reader_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        import time

        deadline = time.monotonic() + self.timeout
        last_error: Optional[Exception] = None

        while time.monotonic() < deadline:
            try:
                self._websocket, _ = await WebSocketClient(self.ws_url).connect()
                self._reader_task = asyncio.create_task(self._reader_loop())
                return
            except (OSError, ConnectionError) as e:
                last_error = e
                await asyncio.sleep(1)

        raise ConnectionError(f"Could not connect to {self.ws_url} within {self.timeout}s: {last_error}")

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._websocket:
            await self._websocket.close()
            self._websocket = None

    async def send_command(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        cmd_id = next(self._id_counter)
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[cmd_id] = future

        message = { "id": cmd_id, "method": method, "params": params or {} }
        await self._websocket.send_message(message)

        try:
            return await asyncio.wait_for(future, timeout=self.timeout)
        except asyncio.TimeoutError:
            self._pending.pop(cmd_id, None)
            raise TimeoutError(f"CDP command '{method}' timed out after {self.timeout}s")

    def on_event(self, method: str, callback: Callable) -> None:
        self._event_listeners.setdefault(method, []).append(callback)

    def remove_event_listener(self, method: str, callback: Callable) -> None:
        listeners = self._event_listeners.get(method, [])
        if callback in listeners:
            listeners.remove(callback)

    async def _reader_loop(self) -> None:
        try:
            while True:
                message = await self._websocket.receive_message()
                if "id" in message:
                    future = self._pending.pop(message["id"], None)
                    if future and not future.done():
                        if "error" in message:
                            future.set_exception(
                                RuntimeError(f"CDP error: {message['error']}")
                            )
                        else:
                            future.set_result(message.get("result", {}))
                elif "method" in message:
                    for cb in self._event_listeners.get(message["method"], []):
                        asyncio.create_task(cb(message.get("params", {})))
        except asyncio.CancelledError:
            pass
        except Exception:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(
                        ConnectionError("CDP reader loop terminated unexpectedly")
                    )
            self._pending.clear()

    @classmethod
    async def from_url(cls, ws_url: str, timeout: float = 30.0) -> CdpClient:
        """Create a connected CdpClient from an explicit WebSocket URL."""
        instance = cls(ws_url, timeout=timeout)
        await instance.connect()
        return instance

    @classmethod
    async def discover(
        cls,
        url: str,
        target_index: int = 0,
        timeout: float = 30.0,
    ) -> CdpClient:
        """Discover the debugger URL by querying /json on the HTTP DevTools port."""
        import time

        deadline = time.monotonic() + timeout
        last_error: Optional[Exception] = None

        while time.monotonic() < deadline:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{url}/json") as response:
                        targets = await response.json(content_type=None)
                break
            except (aiohttp.ClientError, OSError) as e:
                last_error = e
                await asyncio.sleep(1)
        else:
            raise ConnectionError(f"Could not reach CDP at {url} within {timeout}s: {last_error}")

        page_targets = [ t for t in targets if t.get("type") == "page" ]

        if not page_targets:
            raise ConnectionError(f"No 'page' target found at {url}.")

        if target_index >= len(page_targets):
            raise IndexError(
                f"target_index {target_index} is out of range; "
                f"{len(page_targets)} page target(s) found."
            )

        websocket_url = page_targets[target_index]["webSocketDebuggerUrl"]
        instance = cls(websocket_url, timeout=timeout)
        await instance.connect()

        return instance

    @classmethod
    async def create_tab(
        cls,
        url: str,
        navigate_url: str = "",
        timeout: float = 30.0,
    ) -> tuple[CdpClient, str]:
        """Create a new browser tab via the DevTools HTTP API.

        Returns (connected CdpClient, target_id).
        """
        endpoint = f"{url}/json/new"
        if navigate_url:
            endpoint += f"?{navigate_url}"

        async with aiohttp.ClientSession() as session:
            async with session.put(endpoint) as response:
                target = await response.json(content_type=None)

        target_id = target["id"]
        ws_url = target["webSocketDebuggerUrl"]

        instance = cls(ws_url, timeout=timeout)
        await instance.connect()

        return instance, target_id

    @classmethod
    async def close_tab(cls, url: str, target_id: str) -> None:
        """Close a browser tab via the DevTools HTTP API."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/json/close/{target_id}") as response:
                await response.read()
