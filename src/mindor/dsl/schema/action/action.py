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
    ImageProcessorActionConfig,
    AgentActionConfig,
    WebBrowserActionConfig,
    VideoSceneDetectorActionConfig,
    VideoConverterActionConfig,
    AudioExtractorActionConfig,
    KeyValueStoreActionConfig,
    GraphStoreActionConfig,
    SearchEngineActionConfig
]
