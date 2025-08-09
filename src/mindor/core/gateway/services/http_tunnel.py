from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.gateway import HttpTunnelGatewayConfig, HttpTunnelGatewayDriver
from mindor.core.logger import logging
from ..base import GatewayService, GatewayType, register_gateway
from pyngrok import ngrok
import asyncio

class CommonHttpTunnelGateway:
    def __init__(self, config: HttpTunnelGatewayConfig):
        self.config: HttpTunnelGatewayConfig = config
        self.public_url: Optional[str] = None

    async def serve(self) -> None:
        self.public_url = await self._serve()
        logging.info("HTTP tunnel started on port %d: %s", self.config.port, self.public_url)

    async def shutdown(self) -> None:
        await self._shutdown()
        logging.info("HTTP tunnel stopped on port %d: %s", self.config.port, self.public_url)
        self.public_url = None

    @abstractmethod
    async def _serve(self) -> str:
        pass

    @abstractmethod
    async def _shutdown(self) -> None:
        pass

class NgrokHttpTunnelGateway(CommonHttpTunnelGateway):
    def __init__(self, config: HttpTunnelGatewayConfig):
        super().__init__(config)

        self.tunnel: Optional[ngrok.NgrokTunnel] = None

    async def _serve(self) -> str:
        self.tunnel = await asyncio.to_thread(
            ngrok.connect,
            addr=self.config.port,
            bind_tls=True
        )
        return self.tunnel.public_url

    async def _shutdown(self) -> None:
        if self.tunnel:
            await asyncio.to_thread(ngrok.disconnect, self.tunnel.public_url)
            self.tunnel = None

class CloudflareHttpTunnelGateway(CommonHttpTunnelGateway):
    def __init__(self, config: HttpTunnelGatewayConfig):
        super().__init__(config)

@register_gateway(GatewayType.HTTP_TUNNEL)
class HttpTunnelGateway(GatewayService):
    def __init__(self, id: str, config: HttpTunnelGatewayConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.engine: Optional[CommonHttpTunnelGateway] = None

        self._configure_driver()

    def _configure_driver(self) -> None:
        if self.config.driver == HttpTunnelGatewayDriver.NGROK:
            self.engine = NgrokHttpTunnelGateway(self.config)
            return

        if self.config.driver == HttpTunnelGatewayDriver.CLOUDFLARE:
            self.engine = CloudflareHttpTunnelGateway(self.config)
            return

    def get_context(self) -> Dict[str, Any]:
        return {
            "public_url": self.engine.public_url,
            "port": self.config.port
        }

    async def _serve(self) -> None:
        await self.engine.serve()

    async def _shutdown(self) -> None:
        await self.engine.shutdown()
