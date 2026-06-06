from typing import Any, Optional
from mindor.dsl.schema.component import WebSocketServerComponentConfig
from mindor.dsl.schema.action import ActionConfig, WebSocketServerActionConfig
from mindor.dsl.schema.action.impl.websocket_server import WebSocketReceiveFormat
from mindor.core.utils.websocket_client import WebSocketClient, WebSocketConnection
from mindor.core.utils.streaming import BytesStreamResource
from mindor.core.utils.shell import run_command_foreground
from mindor.core.utils.time import parse_duration
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
import asyncio, json

class WebSocketServerAction:
    def __init__(self, config: WebSocketServerActionConfig):
        self.config: WebSocketServerActionConfig = config

    async def run(self, context: ComponentActionContext, client: WebSocketClient) -> Any:
        path    = await context.render_variable(self.config.path)
        params  = await context.render_variable(self.config.params)
        headers = await context.render_variable(self.config.headers)
        message = await context.render_variable(self.config.message)

        format  = await context.render_variable(self.config.receive.format)
        collect = await context.render_variable(self.config.receive.collect)
        timeout_str = await context.render_variable(self.config.receive.timeout)
        timeout = parse_duration(timeout_str) if timeout_str else None

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
                return self._receive_stream(connection, format, context, owned)

            if collect:
                response = await self._receive_collect(connection, format)
            else:
                response = await self._receive_single(connection, format)
        except:
            if owned:
                await connection.close()
            raise

        if owned:
            await connection.close()

        if format == WebSocketReceiveFormat.BINARY and isinstance(response, (bytes, bytearray)):
            response = BytesStreamResource(bytes(response), "application/octet-stream")

        context.register_source("response", response)
        return (await context.render_variable(self.config.output)) if self.config.output else response

    async def _send(self, connection: WebSocketConnection, message: Any) -> None:
        if isinstance(message, (dict, list)):
            await connection.send_message(message)
        elif isinstance(message, bytes):
            await connection.send_bytes(message)
        else:
            await connection.websocket.send(str(message))

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

    async def _receive_stream(self, connection: WebSocketConnection, format: WebSocketReceiveFormat, context: ComponentActionContext, owned: bool = False):
        try:
            async for frame in connection.receive_frames():
                frame = self._decode_frame(frame, format)
                if frame is not None:
                    context.register_source("response[]", frame)
                    yield await context.render_variable(self.config.output)
        finally:
            if owned:
                await connection.close()

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

        self.client: Optional[WebSocketClient] = None

    async def _setup(self) -> None:
        if self.config.manage.scripts.install:
            for command in self.config.manage.scripts.install:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

        if self.config.manage.scripts.build:
            for command in self.config.manage.scripts.build:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

    async def _teardown(self):
        if self.config.manage.scripts.clean:
            for command in self.config.manage.scripts.clean:
                await run_command_foreground(command, self.config.manage.working_dir, self.config.manage.env)

    async def _start(self) -> None:
        base_url = f"ws://localhost:{self.config.port}" + (self.config.base_path or "")
        self.client = WebSocketClient(
            base_url=base_url,
            ping_interval=parse_duration(self.config.ping_interval) if self.config.ping_interval else None,
            ping_timeout=parse_duration(self.config.ping_timeout) if self.config.ping_timeout else None,
            additional_headers=self.config.headers or None,
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
            await run_command_foreground(self.config.manage.scripts.start, self.config.manage.working_dir, self.config.manage.env)

    async def _is_ready(self) -> bool:
        try:
            reader, writer = await asyncio.open_connection("localhost", self.config.port)
            writer.write(b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            response = await asyncio.wait_for(reader.read(12), timeout=2)
            writer.close()
            await writer.wait_closed()
            return response.startswith(b"HTTP/")
        except Exception:
            return False

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WebSocketServerAction(action).run(context, self.client)
