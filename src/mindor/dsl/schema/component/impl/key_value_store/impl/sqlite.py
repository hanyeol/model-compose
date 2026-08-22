from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import SqliteKeyValueStoreActionConfig
from .common import CommonKeyValueStoreComponentConfig, KeyValueStoreDriver

class SqliteKeyValueStoreComponentConfig(CommonKeyValueStoreComponentConfig):
    driver: Literal[KeyValueStoreDriver.SQLITE]
    path: str = Field(default="kv-store.sqlite", description="Filesystem path to the SQLite database file; ':memory:' uses an in-memory database.")
    table: str = Field(default="kv_store", description="Name of the table used to store key-value entries.")
    actions: List[SqliteKeyValueStoreActionConfig] = Field(default_factory=list)
