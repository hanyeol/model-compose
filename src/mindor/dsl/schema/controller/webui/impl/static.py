from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonWebUIConfig, ControllerWebUIDriver

class StaticWebUIConfig(CommonWebUIConfig):
    driver: Literal[ControllerWebUIDriver.STATIC]
    static_dir: str = Field(default="webui", description="Directory containing static HTML/CSS/JS files for the web UI.")
