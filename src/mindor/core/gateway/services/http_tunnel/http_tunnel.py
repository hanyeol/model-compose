from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.gateway import HttpTunnelGatewayConfig, HttpTunnelGatewayDriver
from ...base import GatewayService, GatewayType, register_gateway
from .base import GatewayService, CommonHttpTunnelGateway
from .drivers import NgrokHttpTunnelGateway, CloudflareHttpTunnelGateway

@register_gateway(GatewayType.HTTP_TUNNEL)
class HttpTunnelGateway(GatewayService):
    config: HttpTunnelGatewayConfig

    def __init__(self, id: str, config: HttpTunnelGatewayConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.driver: Optional[CommonHttpTunnelGateway] = None

        self._configure_driver()

    def _configure_driver(self) -> None:
        if self.config.driver == HttpTunnelGatewayDriver.NGROK:
            self.driver = NgrokHttpTunnelGateway(self.config)
            return

        if self.config.driver == HttpTunnelGatewayDriver.CLOUDFLARE:
            self.driver = CloudflareHttpTunnelGateway(self.config)
            return

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.driver.get_setup_requirements()

    def get_context(self) -> Dict[str, Any]:
        return {
            "public_url": self.driver.public_url,
            "port": self.config.port
        }

    async def _serve(self) -> None:
        await self.driver.serve()

    async def _shutdown(self) -> None:
        await self.driver.shutdown()
