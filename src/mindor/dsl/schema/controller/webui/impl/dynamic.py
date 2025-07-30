from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonWebUIConfig, ControllerWebUIDriver

class DynamicWebUIConfig(CommonWebUIConfig):
    driver: Literal[ControllerWebUIDriver.DYNAMIC]
    command: str = Field(..., description="Command to start the web UI server.")
    server_dir: str = Field(default="webui/server", description="Directory containing source code and entry point for the web UI server.")
    static_dir: str = Field(default="webui/static", description="Directory containing static HTML/CSS/JS files for the web UI.")
