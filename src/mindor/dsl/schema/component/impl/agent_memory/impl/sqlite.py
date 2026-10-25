from typing import Literal
from pydantic import Field
from .common import CommonAgentMemoryStorageConfig, AgentMemoryStorageDriverType

class SqliteAgentMemoryStorageConfig(CommonAgentMemoryStorageConfig):
    driver: Literal[AgentMemoryStorageDriverType.SQLITE] = Field(default=AgentMemoryStorageDriverType.SQLITE, description="SQLite storage backend for agent memory.")
    path: str = Field(default=".agent-memory.db", description="Filesystem path to the SQLite database file.")
