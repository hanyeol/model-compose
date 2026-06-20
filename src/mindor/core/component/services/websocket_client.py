from typing import Any, Optional
from mindor.dsl.schema.component import WebSocketClientComponentConfig
from mindor.dsl.schema.action import ActionConfig, WebSocketClientActionConfig
from mindor.dsl.schema.action.impl.websocket_server import WebSocketReceiveFormat
from mindor.core.utils.websocket_client import WebSocketClient, WebSocketConnection
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.core.utils.time import parse_duration
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
import json

class WebSocketClientAction:
    def __init__(self, config: WebSocketClientActionConfig):
        self.config: WebSocketClientActionConfig = config

    async def run(self, context: ComponentActionContext, client: WebSocketClient) -> Any:
        path    = await context.render_variable(self.config.path)
        params  = await context.render_variable(self.config.params)
        headers = await context.render_variable(self.config.headers)
        message = await context.render_variable(self.config.message)

        format  = await context.render_variable(self.config.receive.format)
        collect = await context.render_variable(self.config.receive.collect)
        timeout = parse_duration(await context.render_variable(self.config.receive.timeout)) if self.config.receive.timeout else None

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

@register_component(ComponentType.WEBSOCKET_CLIENT)
class WebSocketClientComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: WebSocketClientComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.client: Optional[WebSocketClient] = None

    async def _start(self) -> None:
        self.client = WebSocketClient(
            base_url=self.config.base_url,
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

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WebSocketClientAction(action).run(context, self.client)
