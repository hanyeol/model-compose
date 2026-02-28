from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import DatasetsActionConfig
from ..common import CommonComponentConfig, ComponentType

class DatasetsComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.DATASETS]
    actions: List[DatasetsActionConfig] = Field(default_factory=list)
