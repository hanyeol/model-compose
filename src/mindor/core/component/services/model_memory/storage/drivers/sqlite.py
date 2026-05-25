from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Tuple, Optional, List, Any
from mindor.dsl.schema.component import SqliteModelMemoryStorageConfig, ModelMemoryStorageDriver
from ..base import ModelMemoryStorage, register_model_memory_storage
import json

if TYPE_CHECKING:
    import aiosqlite

@register_model_memory_storage(ModelMemoryStorageDriver.SQLITE)
class SqliteModelMemoryStorage(ModelMemoryStorage):
    def __init__(self, config: SqliteModelMemoryStorageConfig):
        self.config: SqliteModelMemoryStorageConfig = config
        self.database: Optional[aiosqlite.Connection] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "aiosqlite" ]

    async def setup(self) -> None:
        import aiosqlite

        self.database = await aiosqlite.connect(self.config.path)
        await self.database.execute("""
            CREATE TABLE IF NOT EXISTS model_memory_sessions (
                session_id TEXT PRIMARY KEY,
                turns TEXT NOT NULL DEFAULT '[]',
                summary TEXT NOT NULL DEFAULT ''
            )
        """)
        await self.database.commit()

    async def close(self) -> None:
        if self.database:
            await self.database.close()
            self.database = None

    async def load(self, session_id: str) -> Tuple[List[List[Any]], str]:
        cursor = await self.database.execute(
            "SELECT turns, summary FROM model_memory_sessions WHERE session_id = ?",
            ( session_id, )
        )
        row = await cursor.fetchone()

        if row is None:
            return [], ""

        return json.loads(row[0]), row[1] or ""

    async def save(self, session_id: str, turns: List[List[Any]], summary: str) -> None:
        await self.database.execute(
            """
            INSERT INTO model_memory_sessions (session_id, turns, summary)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET turns = excluded.turns, summary = excluded.summary
            """,
            ( session_id, json.dumps(turns, ensure_ascii=False), summary )
        )
        await self.database.commit()

    async def delete(self, session_id: str) -> None:
        await self.database.execute(
            "DELETE FROM model_memory_sessions WHERE session_id = ?",
            ( session_id, )
        )
        await self.database.commit()
