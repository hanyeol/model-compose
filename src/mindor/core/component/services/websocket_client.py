from typing import Any, Optional
from mindor.dsl.schema.component import WebSocketClientComponentConfig
from mindor.dsl.schema.action import ActionConfig, WebSocketClientActionConfig
from mindor.core.utils.websocket_client import WebSocketClient
from mindor.core.utils.time import parse_duration
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
from .websocket_server import WebSocketConnector, WebSocketServerAction

class WebSocketClientAction(WebSocketServerAction):
    def __init__(self, config: WebSocketClientActionConfig):
        super().__init__(config)

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
        self.client: Optional[WebSocketConnector] = None

    async def _start(self) -> None:
        self.client = WebSocketConnector(
            WebSocketClient(
                base_url=self.config.base_url,
                ping_interval=parse_duration(self.config.ping_interval).total_seconds() if self.config.ping_interval else None,
                ping_timeout=parse_duration(self.config.ping_timeout).total_seconds() if self.config.ping_timeout else None,
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

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WebSocketClientAction(action).run(context, self.client)
