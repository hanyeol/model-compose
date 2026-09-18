from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonWebUIConfig, ControllerWebUIDriverType

class StaticWebUIConfig(CommonWebUIConfig):
    driver: Literal[ControllerWebUIDriverType.STATIC]
    static_dir: str = Field(default="webui", description="Directory containing static HTML, CSS, and JS assets.")
