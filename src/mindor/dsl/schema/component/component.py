from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

ComponentConfig = Annotated[
    Union[
        HttpServerComponentConfig,
        HttpClientComponentConfig,
        WebSocketServerComponentConfig,
        WebSocketClientComponentConfig,
        McpServerComponentConfig,
        McpClientComponentConfig,
        ModelComponentConfig,
        ModelMemoryComponentConfig,
        ModelTokenizerComponentConfig,
        DatasetsComponentConfig,
        VectorStoreComponentConfig,
        WorkflowComponentConfig,
        ShellComponentConfig,
        TextSplitterComponentConfig,
        ImageProcessorComponentConfig,
        VectorProcessorComponentConfig,
        WebScraperComponentConfig,
        AgentComponentConfig,
        WebBrowserComponentConfig,
        VideoSceneDetectorComponentConfig,
        VideoConverterComponentConfig,
        VideoFrameExtractorComponentConfig,
        AudioExtractorComponentConfig,
        AudioConverterComponentConfig,
        AudioFeatureExtractorComponentConfig,
        KeyValueStoreComponentConfig,
        GraphStoreComponentConfig,
        FileStoreComponentConfig,
        SearchEngineComponentConfig
    ],
    Field(discriminator="type")
]
