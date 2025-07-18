from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.gateway import GatewayConfig
from .base import GatewayService, GatewayRegistry

GatewayInstances: Dict[str, GatewayService] = {}

def create_gateway(id: str, config: GatewayConfig, daemon: bool) -> GatewayService:
    try:
        gateway = GatewayInstances[id] if id in GatewayInstances else None

        if not gateway:
            if not GatewayRegistry:
                from . import services
            gateway = GatewayRegistry[config.type](id, config, daemon)
            GatewayInstances[id] = gateway

        return gateway
    except KeyError:
        raise ValueError(f"Unsupported gateway type: {config.type}")

def find_gateway_by_port(port: int) -> Optional[GatewayService]:
    for gateway in GatewayInstances.values():
        if gateway.config.port == port:
            return gateway
    return None
