from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.gateway import HttpTunnelGatewayConfig
from mindor.core.logger import logging

class CommonHttpTunnelGateway:
    def __init__(self, config: HttpTunnelGatewayConfig):
        self.config: HttpTunnelGatewayConfig = config
        self.public_urls = Optional[Dict[int, str]]

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def serve(self) -> None:
        self.public_urls = await self._serve()

        for port, public_url in (self.public_urls or {}).items():
            logging.info("HTTP tunnel started on port %d: %s", port, public_url)

    async def shutdown(self) -> None:
        await self._shutdown()

        for port, public_url in (self.public_urls or {}).items():
            logging.info("HTTP tunnel stopped on port %d: %s", port, public_url)

        self.public_urls = None

    def get_public_url(self, port: int) -> Optional[str]:
        if self.public_urls:
            return self.public_urls.get(port)

        return None

    @abstractmethod
    async def _serve(self) -> Optional[Dict[int, str]]:
        pass

    @abstractmethod
    async def _shutdown(self) -> None:
        pass
