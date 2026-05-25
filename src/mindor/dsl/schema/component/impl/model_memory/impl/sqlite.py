from typing import Literal
from pydantic import Field
from .common import CommonModelMemoryStorageConfig, ModelMemoryStorageDriver

class SqliteModelMemoryStorageConfig(CommonModelMemoryStorageConfig):
    driver: Literal[ModelMemoryStorageDriver.SQLITE] = Field(default=ModelMemoryStorageDriver.SQLITE, description="SQLite storage driver.")
    path: str = Field(default=".model-memory.db", description="SQLite database file path.")
