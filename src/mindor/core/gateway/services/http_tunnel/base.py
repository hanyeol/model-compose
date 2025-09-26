from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.gateway import HttpTunnelGatewayConfig
from mindor.core.logger import logging

class CommonHttpTunnelGateway:
    def __init__(self, config: HttpTunnelGatewayConfig):
        self.config: HttpTunnelGatewayConfig = config
        self.public_url: Optional[str] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

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
