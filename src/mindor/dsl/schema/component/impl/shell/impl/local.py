from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import LocalShellActionConfig
from .common import CommonShellComponentConfig, ShellDriver

class LocalShellComponentConfig(CommonShellComponentConfig):
    driver: Literal[ShellDriver.LOCAL]
    actions: List[LocalShellActionConfig] = Field(default_factory=list)
