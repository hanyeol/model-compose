from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

ComponentConfig = Annotated[
    Union[ 
        HttpServerComponentConfig, 
        HttpClientComponentConfig,
        McpServerComponentConfig,
        McpClientComponentConfig,
        ModelComponentConfig,
        WorkflowComponentConfig,
        ShellComponentConfig
    ],
    Field(discriminator="type")
]
