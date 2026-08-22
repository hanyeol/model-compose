from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import SqliteKeyValueStoreComponentConfig
from mindor.dsl.schema.action import KeyValueStoreActionConfig, SqliteKeyValueStoreActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.sql import validate_identifier
from ..base import KeyValueStoreService, KeyValueStoreDriver, register_kv_store_service
from ..base import ComponentActionContext
from .common import KeyValueStoreAction
import json, time

if TYPE_CHECKING:
    from aiosqlite import Connection as AsyncConnection

class SqliteKeyValueStoreAction(KeyValueStoreAction):
    def __init__(self, config: SqliteKeyValueStoreActionConfig, connection: AsyncConnection, table: str):
        super().__init__(config)

        self.connection: AsyncConnection = connection
        self.table: str = table

    async def _get(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        values = await self._select_active_values(keys)
        value_map = { key: value for key, value in values }

        return [ { "key": key, "value": value_map.get(key) } for key in keys ]

    async def _set(
        self,
        keys: List[str],
        values: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        expires_at = (time.time() + params["ttl"]) if params["ttl"] is not None else None
        rows = [ (key, self._encode_value(value), expires_at) for key, value in zip(keys, values) ]

        await self.connection.executemany(
            f"INSERT INTO {self.table} (key, value, expires_at) VALUES (?, ?, ?) "
            f"ON CONFLICT(key) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at",
            rows,
        )
        await self.connection.commit()

        return [ { "key": key, "success": True } for key in keys ]

    async def _delete(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        # Compute per-key deletion status before the DELETE runs; an expired
        # row physically exists but should report as not-deleted.
        active_keys = await self._select_active_keys(keys)

        await self.connection.executemany(
            f"DELETE FROM {self.table} WHERE key = ?",
            [ (key,) for key in keys ],
        )
        await self.connection.commit()

        return [ { "key": key, "deleted": key in active_keys } for key in keys ]

    async def _exists(
        self,
        keys: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[Dict[str, Any]]:
        active_keys = await self._select_active_keys(keys)

        return [ { "key": key, "exists": key in active_keys } for key in keys ]

    async def _select_active_keys(self, keys: List[str]) -> set:
        if not keys:
            return set()

        placeholders = ",".join("?" * len(keys))
        now = time.time()

        async with self.connection.execute(
            f"SELECT key FROM {self.table} "
            f"WHERE key IN ({placeholders}) AND (expires_at IS NULL OR expires_at > ?)",
            (*keys, now),
        ) as cursor:
            rows = await cursor.fetchall()

        return { key for (key,) in rows }

    async def _select_active_values(self, keys: List[str]) -> List[tuple]:
        if not keys:
            return []

        placeholders = ",".join("?" * len(keys))
        now = time.time()

        async with self.connection.execute(
            f"SELECT key, value FROM {self.table} "
            f"WHERE key IN ({placeholders}) AND (expires_at IS NULL OR expires_at > ?)",
            (*keys, now),
        ) as cursor:
            rows = await cursor.fetchall()

        return [ (key, self._decode_value(value)) for key, value in rows ]

    def _decode_value(self, value: Any) -> Any:
        if value is None:
            return None

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def _encode_value(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)

        if not isinstance(value, str):
            return str(value)

        return value

@register_kv_store_service(KeyValueStoreDriver.SQLITE)
class SqliteKeyValueStoreService(KeyValueStoreService):
    def __init__(self, id: str, config: SqliteKeyValueStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        validate_identifier(self.config.table, kind="sqlite table")

        self.connection: Optional[AsyncConnection] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "aiosqlite" ]

    async def _start(self) -> None:
        import aiosqlite

        self.connection = await aiosqlite.connect(self.config.path)

        # WAL enables concurrent readers alongside a single writer and keeps
        # writes off the main DB file until checkpoint. NORMAL sync trades a
        # tiny durability window for much lower write latency — appropriate
        # for a cache-shaped workload.
        await self.connection.execute("PRAGMA journal_mode=WAL")
        await self.connection.execute("PRAGMA synchronous=NORMAL")
        await self.connection.execute(
            f"CREATE TABLE IF NOT EXISTS {self.config.table} ("
            f"  key TEXT PRIMARY KEY,"
            f"  value TEXT,"
            f"  expires_at REAL"
            f")"
        )
        await self.connection.commit()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.connection:
            await self.connection.close()
            self.connection = None

    async def _run(self, action: KeyValueStoreActionConfig, context: ComponentActionContext) -> Any:
        return await SqliteKeyValueStoreAction(action, self.connection, self.config.table).run(context)
