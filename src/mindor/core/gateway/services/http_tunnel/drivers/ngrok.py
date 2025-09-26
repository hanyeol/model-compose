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

        self.tunnel: Optional[ngrok.NgrokTunnel] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pyngrok" ]

    async def _serve(self) -> str:
        from pyngrok import ngrok

        self.tunnel = await asyncio.to_thread(
            ngrok.connect,
            addr=self.config.port,
            bind_tls=True
        )
        return self.tunnel.public_url

    async def _shutdown(self) -> None:
        from pyngrok import ngrok

        if self.tunnel:
            await asyncio.to_thread(ngrok.disconnect, self.tunnel.public_url)
            self.tunnel = None
