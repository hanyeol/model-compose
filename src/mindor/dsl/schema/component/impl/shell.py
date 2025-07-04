from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import ShellActionConfig
from .common import ComponentType, CommonComponentConfig

class ShellComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SHELL]
    base_dir: Optional[str] = Field(default=None, description="Base working directory for all actions in this component.")
    actions: Optional[Dict[str, ShellActionConfig]] = Field(default_factory=dict)
