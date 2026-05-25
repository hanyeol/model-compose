from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import SQLiteSearchEngineActionConfig
from .common import CommonSearchEngineComponentConfig, SearchEngineDriver

class SQLiteSearchEngineComponentConfig(CommonSearchEngineComponentConfig):
    driver: Literal[SearchEngineDriver.SQLITE]
    storage_dir: str = Field(default="./sqlite-search", description="Directory where the SQLite database file is stored.")
    database: str = Field(default="search.db", description="SQLite database file name. Multiple indexes are stored as virtual tables in the same database.")
    actions: List[SQLiteSearchEngineActionConfig] = Field(default_factory=list)
