from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonWebUIConfig, ControllerWebUIDriver

class DynamicWebUIConfig(CommonWebUIConfig):
    driver: Literal[ControllerWebUIDriver.DYNAMIC]
    command: str = Field(..., description="Shell command that starts the Web UI server.")
    server_dir: str = Field(default="webui/server", description="Directory containing the Web UI server source and entry point.")
    static_dir: str = Field(default="webui/static", description="Directory containing static HTML, CSS, and JS assets.")
