from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonComponentConfig, ComponentType

class KeyValueStoreDriver(str, Enum):
    REDIS = "redis"

class CommonKeyValueStoreComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.KEY_VALUE_STORE]
    driver: KeyValueStoreDriver = Field(..., description="Key-value store backend driver.")
