from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Iterator, Any
from mindor.dsl.schema.gateway import HttpTunnelGatewayConfig
from ..base import CommonHttpTunnelGateway
import asyncio

if TYPE_CHECKING:
    pass

class CloudflareHttpTunnelGateway(CommonHttpTunnelGateway):
    def __init__(self, config: HttpTunnelGatewayConfig):
        super().__init__(config)
