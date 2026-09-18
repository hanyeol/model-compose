from typing import Literal
from pydantic import Field
from .common import CommonModelMemoryStorageConfig, ModelMemoryStorageDriverType

class SqliteModelMemoryStorageConfig(CommonModelMemoryStorageConfig):
    driver: Literal[ModelMemoryStorageDriverType.SQLITE] = Field(default=ModelMemoryStorageDriverType.SQLITE, description="SQLite storage backend for model memory.")
    path: str = Field(default=".model-memory.db", description="Filesystem path to the SQLite database file.")
