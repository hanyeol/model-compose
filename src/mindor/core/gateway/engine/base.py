from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import abstractmethod
from mindor.dsl.schema.gateway import GatewayConfig, GatewayType
from mindor.core.services import AsyncService

class GatewayEngine(AsyncService):
    def __init__(self, id: str, config: GatewayConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: GatewayConfig = config

    @abstractmethod
    def get_context(self) -> Dict[str, Any]:
        pass

GatewayEngineMap: Dict[GatewayType, Type[GatewayEngine]] = {}
