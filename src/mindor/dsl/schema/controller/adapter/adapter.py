from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import HttpServerControllerAdapterConfig, McpServerControllerAdapterConfig, QueueSubscriberControllerAdapterConfig

ControllerAdapterConfig = Annotated[
    Union[
        HttpServerControllerAdapterConfig,
        McpServerControllerAdapterConfig,
        QueueSubscriberControllerAdapterConfig
    ],
    Field(discriminator="type")
]
