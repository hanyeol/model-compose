from typing import Any, Optional, Dict, Tuple
from mindor.dsl.schema.component import WebSocketServerComponentConfig
from mindor.dsl.schema.action import ActionConfig, WebSocketServerActionConfig
from mindor.dsl.schema.action.impl.websocket_server import WebSocketReceiveFormat
from mindor.core.utils.websocket_client import WebSocketClient, WebSocketConnection
from mindor.core.utils.streaming import BytesStreamResource
from mindor.core.utils.shell import run_command_streaming
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
import asyncio, json

class WebSocketConnector:
    def __init__(self, client: WebSocketClient, params: Optional[Dict[str, Any]] = None):
        self._client: WebSocketClient = client
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
            connection = await self._client.connect(
                path=path,
                params={ **(self._params or {}), **(params or {}) } or None,
                headers=headers,
                receive_timeout=receive_timeout
            )
            return connection, True
        if not self._connection or not self._connection.is_connected():
            self._connection = await self._client.connect()
        return self._connection, False

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

class WebSocketServerAction:
    def __init__(self, config: WebSocketServerActionConfig):
        self.config: WebSocketServerActionConfig = config

    async def run(self, context: ComponentActionContext, client: WebSocketConnector) -> Any:
        path    = await context.render_variable(self.config.path)
        params  = await context.render_variable(self.config.params)
        headers = await context.render_variable(self.config.headers)
        message = await context.render_variable(self.config.message)

        format  = await context.render_variable(self.config.receive.format)
        collect = await context.render_variable(self.config.receive.collect)
        timeout = await context.render_variable(self.config.receive.timeout)

        connection, owned = await client.connect(
            path=path,
            params=params or None,
            headers=headers or None,
            receive_timeout=timeout
        )

        try:
            if message:
                await self._send(connection, message)

            if context.contains_variable_reference("response[]", self.config.output):
                return self._receive_stream(connection, format, context)

            response = await self._receive(connection, format, collect)
        except:
            if owned:
                await connection.close()
            raise

        if owned:
            await connection.close()

        if format == WebSocketReceiveFormat.BINARY and isinstance(response, (bytes, bytearray)):
            response = BytesStreamResource(bytes(response), "application/octet-stream")

        context.register_source("response", response)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else response

    async def _send(self, connection: WebSocketConnection, message: Any) -> None:
        if isinstance(message, (dict, list)):
            await connection.send_message(message)
        elif isinstance(message, bytes):
            await connection.send_bytes(message)
        else:
            await connection.websocket.send(str(message))

    async def _receive(self, connection: WebSocketConnection, format: WebSocketReceiveFormat, collect: bool) -> Any:
        if collect:
            return await self._receive_collect(connection, format)
        return await self._receive_single(connection, format)

    async def _receive_collect(self, connection: WebSocketConnection, format: WebSocketReceiveFormat) -> Any:
        if format == WebSocketReceiveFormat.BINARY:
            buffer = bytearray()
            async for frame in connection.receive_frames():
                if isinstance(frame, bytes):
                    buffer.extend(frame)
            return bytes(buffer)
        items = []
        async for frame in connection.receive_frames():
            if isinstance(frame, str):
                if format == WebSocketReceiveFormat.JSON:
                    try:
                        items.append(json.loads(frame))
                    except json.JSONDecodeError:
                        pass
                else:
                    items.append(frame)
        return items

    async def _receive_single(self, connection: WebSocketConnection, format: WebSocketReceiveFormat) -> Any:
        async for frame in connection.receive_frames():
            frame = self._decode_frame(frame, format)
            if frame is not None:
                return frame
        return None

    async def _receive_stream(self, connection: WebSocketConnection, format: WebSocketReceiveFormat, context: ComponentActionContext):
        async for frame in connection.receive_frames():
            frame = self._decode_frame(frame, format)
            if frame is not None:
                context.register_source("response[]", frame)
                yield await context.render_variable(self.config.output, ignore_files=True)

    def _decode_frame(self, frame: Any, format: WebSocketReceiveFormat) -> Any:
        if format == WebSocketReceiveFormat.BINARY and isinstance(frame, bytes):
            return frame
        if format == WebSocketReceiveFormat.JSON and isinstance(frame, str):
            try:
                return json.loads(frame)
            except json.JSONDecodeError:
                return None
        if format == WebSocketReceiveFormat.TEXT and isinstance(frame, str):
            return frame
        return None

@register_component(ComponentType.WEBSOCKET_SERVER)
class WebSocketServerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: WebSocketServerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.client: Optional[WebSocketConnector] = None

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            for command in self.config.manage.scripts.install:
                await run_command_streaming(command, self.config.manage.working_dir, self.config.manage.env)

        if self.config.manage.scripts.build:
            for command in self.config.manage.scripts.build:
                await run_command_streaming(command, self.config.manage.working_dir, self.config.manage.env)

    async def _teardown(self):
        if self.config.manage.scripts.clean:
            for command in self.config.manage.scripts.clean:
                await run_command_streaming(command, self.config.manage.working_dir, self.config.manage.env)

    async def _start(self) -> None:
        base_url = f"ws://localhost:{self.config.port}" + (self.config.base_path or "")
        self.client = WebSocketConnector(
            WebSocketClient(
                base_url=base_url,
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout,
                additional_headers=self.config.headers or None
            ),
            params=self.config.params or None
        )
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        if self.client:
            await self.client.close()
            self.client = None

    async def _serve(self) -> None:
        if self.config.manage.scripts.start:
            await run_command_streaming(self.config.manage.scripts.start, self.config.manage.working_dir, self.config.manage.env)

    async def _is_ready(self) -> bool:
        try:
            _, writer = await asyncio.open_connection("localhost", self.config.port)
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError):
            return False

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WebSocketServerAction(action).run(context, self.client)
