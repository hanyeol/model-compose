from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import MemoryKeyValueStoreActionConfig
from .common import CommonKeyValueStoreComponentConfig, KeyValueStoreDriver

class MemoryKeyValueStoreComponentConfig(CommonKeyValueStoreComponentConfig):
    driver: Literal[KeyValueStoreDriver.MEMORY]
    actions: List[MemoryKeyValueStoreActionConfig] = Field(default_factory=list)
