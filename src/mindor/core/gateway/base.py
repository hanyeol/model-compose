from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import abstractmethod
from mindor.dsl.schema.gateway import GatewayConfig, GatewayType
from mindor.core.services import AsyncService

class GatewayService(AsyncService):
    def __init__(self, id: str, config: GatewayConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: GatewayConfig = config

    @abstractmethod
    def get_context(self) -> Dict[str, Any]:
        pass

def register_gateway(type: GatewayType):
    def decorator(cls: Type[GatewayService]) -> Type[GatewayService]:
        GatewayRegistry[type] = cls
        return cls
    return decorator

GatewayRegistry: Dict[GatewayType, Type[GatewayService]] = {}
