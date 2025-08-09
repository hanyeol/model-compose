from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

HttpTunnelGatewayConfig = Annotated[
    Union[ 
        NgrokHttpTunnelGatewayConfig,
        CloudflareHttpTunnelGatewayConfig,
    ],
    Field(discriminator="driver")
]
