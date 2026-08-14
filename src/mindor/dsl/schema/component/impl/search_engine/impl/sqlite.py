from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import SQLiteSearchEngineActionConfig
from .common import CommonSearchEngineComponentConfig, SearchEngineDriver

class SQLiteSearchEngineComponentConfig(CommonSearchEngineComponentConfig):
    driver: Literal[SearchEngineDriver.SQLITE]
    storage_dir: str = Field(default="./sqlite-search", description="Directory that holds the SQLite database file.")
    database: str = Field(default="search.db", description="Filename of the SQLite database within `storage_dir`.")
    actions: List[SQLiteSearchEngineActionConfig] = Field(default_factory=list)
