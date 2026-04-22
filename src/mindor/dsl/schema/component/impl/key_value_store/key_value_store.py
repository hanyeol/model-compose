from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .impl import *

KeyValueStoreComponentConfig = Annotated[
    Union[
        RedisKeyValueStoreComponentConfig
    ],
    Field(discriminator="driver")
]
