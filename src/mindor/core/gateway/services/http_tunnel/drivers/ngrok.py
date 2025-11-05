from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import HttpTunnelGatewayConfig
from ..base import CommonHttpTunnelGateway
import asyncio

if TYPE_CHECKING:
    from pyngrok import ngrok

class NgrokHttpTunnelGateway(CommonHttpTunnelGateway):
    def __init__(self, config: HttpTunnelGatewayConfig):
        super().__init__(config)

        self.tunnels: Optional[Dict[int, ngrok.NgrokTunnel]] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pyngrok" ]

    async def _serve(self) -> Optional[Dict[int, str]]:
        from pyngrok import ngrok

        self.tunnels = {}

        for port in self.config.port:
            self.tunnels[port] = await asyncio.to_thread(
                ngrok.connect,
                addr=port,
                bind_tls=True
            )
        
        return { port: tunnel.public_url for port, tunnel in self.tunnels.items() }

    async def _shutdown(self) -> None:
        from pyngrok import ngrok

        for tunnel in self.tunnels.values():
            await asyncio.to_thread(ngrok.disconnect, tunnel.public_url)

        self.tunnels = None
