from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonSearchIndexActionConfig,
    CommonSearchSearchActionConfig,
    CommonSearchDeleteActionConfig
)

class SQLiteSearchIndexActionConfig(CommonSearchIndexActionConfig):
    pass

class SQLiteSearchSearchActionConfig(CommonSearchSearchActionConfig):
    pass

class SQLiteSearchDeleteActionConfig(CommonSearchDeleteActionConfig):
    pass

SQLiteSearchEngineActionConfig = Annotated[
    Union[
        SQLiteSearchIndexActionConfig,
        SQLiteSearchSearchActionConfig,
        SQLiteSearchDeleteActionConfig
    ],
    Field(discriminator="method")
]
