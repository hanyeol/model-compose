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
        SentenceSplitterComponentConfig,
        ImageProcessorComponentConfig,
        VectorProcessorComponentConfig,
        WebScraperComponentConfig,
        AgentComponentConfig,
        WebBrowserComponentConfig,
        VideoSceneDetectorComponentConfig,
        VideoConverterComponentConfig,
        VideoEncoderComponentConfig,
        VideoFrameExtractorComponentConfig,
        ScreenCaptureComponentConfig,
        RtmpPublisherComponentConfig,
        AudioExtractorComponentConfig,
        AudioConverterComponentConfig,
        AudioProcessorComponentConfig,
        AudioFeatureExtractorComponentConfig,
        KeyValueStoreComponentConfig,
        GraphStoreComponentConfig,
        FileStoreComponentConfig,
        SearchEngineComponentConfig
    ],
    Field(discriminator="type")
]
