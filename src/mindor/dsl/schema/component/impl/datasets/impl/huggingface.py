from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import DatasetsDriver, HuggingfaceDatasetsActionConfig
from .common import CommonDatasetsComponentConfig

class HuggingfaceDatasetsComponentConfig(CommonDatasetsComponentConfig):
    driver: Literal[DatasetsDriver.HUGGINGFACE]
    actions: List[HuggingfaceDatasetsActionConfig] = Field(default_factory=list)
