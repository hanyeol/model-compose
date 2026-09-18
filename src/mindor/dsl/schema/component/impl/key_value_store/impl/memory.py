from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import MemoryKeyValueStoreActionConfig
from .common import CommonKeyValueStoreComponentConfig, KeyValueStoreDriverType

class MemoryKeyValueStoreComponentConfig(CommonKeyValueStoreComponentConfig):
    driver: Literal[KeyValueStoreDriverType.MEMORY]
    actions: List[MemoryKeyValueStoreActionConfig] = Field(default_factory=list)
