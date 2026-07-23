from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

ActionConfig = Union[
    HttpServerActionConfig,
    HttpClientActionConfig,
    WebSocketServerActionConfig,
    WebSocketClientActionConfig,
    McpServerActionConfig,
    McpClientActionConfig,
    ModelActionConfig,
    ModelMemoryActionConfig,
    ModelTokenizerActionConfig,
    WorkflowActionConfig,
    ShellActionConfig,
    TextSplitterActionConfig,
    SentenceSplitterActionConfig,
    ImageProcessorActionConfig,
    VectorProcessorActionConfig,
    AgentActionConfig,
    WebBrowserActionConfig,
    VideoSceneDetectorActionConfig,
    VideoConverterActionConfig,
    VideoEncoderActionConfig,
    VideoFrameExtractorActionConfig,
    ScreenCaptureActionConfig,
    RtmpPublisherActionConfig,
    AudioExtractorActionConfig,
    AudioProcessorActionConfig,
    AudioPlaybackActionConfig,
    KeyValueStoreActionConfig,
    GraphStoreActionConfig,
    FileStoreActionConfig,
    SearchEngineActionConfig,
    DataQueueActionConfig
]
