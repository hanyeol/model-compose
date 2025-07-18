from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import SshTunnelGatewayConfig
from ..base import GatewayService, GatewayType, register_gateway
from pyngrok import ngrok

@register_gateway(GatewayType.SSH_TUNNEL)
class SshTunnelGateway(GatewayService):
    def __init__(self, id: str, config: SshTunnelGatewayConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.tunnel: Optional[Any] = None
        self.public_url: Optional[str] = None

    def get_context(self) -> Dict[str, Any]:
        return {
            "public_url": self.public_url,
            "port": self.config.port
        }

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass
