from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .http_server import HttpServerControllerAdapterConfig
from .mcp_server import McpServerControllerAdapterConfig

ControllerAdapterConfig = Annotated[
    Union[
        HttpServerControllerAdapterConfig,
        McpServerControllerAdapterConfig
    ],
    Field(discriminator="type")
]
