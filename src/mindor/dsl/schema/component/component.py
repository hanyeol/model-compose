from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

ComponentConfig = Annotated[
    Union[
        HttpServerComponentConfig,
        HttpClientComponentConfig,
        WebSocketServerComponentConfig,
        McpServerComponentConfig,
        McpClientComponentConfig,
        ModelComponentConfig,
        DatasetsComponentConfig,
        VectorStoreComponentConfig,
        WorkflowComponentConfig,
        ShellComponentConfig,
        TextSplitterComponentConfig,
        ImageProcessorComponentConfig,
        WebScraperComponentConfig,
        AgentComponentConfig,
        WebBrowserComponentConfig,
        VideoSceneDetectorComponentConfig,
        VideoConverterComponentConfig,
        AudioExtractorComponentConfig,
        KeyValueStoreComponentConfig
    ],
    Field(discriminator="type")
]
