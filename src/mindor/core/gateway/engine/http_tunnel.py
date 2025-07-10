from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import HttpTunnelGatewayConfig
from .base import GatewayEngine, GatewayType, GatewayEngineMap
from pyngrok import ngrok

class HttpTunnelGateway(GatewayEngine):
    def __init__(self, id: str, config: HttpTunnelGatewayConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.tunnel: Optional[ngrok.NgrokTunnel] = None
        self.public_url: Optional[str] = None
    
    def get_context(self) -> Dict[str, Any]:
        return {
            "public_url": self.public_url,
            "port": self.config.port
        }

    async def _serve(self) -> None:
        if self.config.driver == "ngrok":
            self.tunnel = ngrok.connect(addr=self.config.port, bind_tls=True)
            self.public_url = self.tunnel.public_url
            return

    async def _shutdown(self) -> None:
        if self.config.driver == "ngrok":
            if self.tunnel:
                ngrok.disconnect(self.tunnel.public_url)
                self.tunnel = None
                self.public_url = None
            return
  
GatewayEngineMap[GatewayType.HTTP_TUNNEL] = HttpTunnelGateway
