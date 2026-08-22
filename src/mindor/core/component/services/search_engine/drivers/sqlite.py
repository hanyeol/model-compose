from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import SQLiteSearchEngineComponentConfig
from mindor.dsl.schema.action import SearchEngineActionConfig, SearchEngineFieldType
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.sql import validate_identifier, quote_identifier, serialize_value
from mindor.core.utils.sqlite import escape_fts_term
from ..base import SearchEngineService, SearchEngineDriver, register_search_engine_service
from ..base import ComponentActionContext
from .common import SearchEngineAction
import sqlite3, os, json, asyncio

if TYPE_CHECKING:
    import aiosqlite

class SQLiteSearchEngineAction(SearchEngineAction):
    def __init__(self, config, database, meta_cache: Dict[str, Any], write_lock: asyncio.Lock):
        super().__init__(config, database)

        self.meta_cache: Dict[str, Any] = meta_cache
        self.write_lock: asyncio.Lock = write_lock

    async def _index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        index = validate_identifier(index, "index")

        async with self.write_lock:
            await self._ensure_meta_table()
            meta = await self._load_meta(index)

            if meta is None:
                if not params["fields"]:
                    raise LookupError(f"Index '{index}' does not exist and no fields were provided.")
                meta = await self._create_index(index, params["fields"])

            column_names = [ field["name"] for field in meta["fields"] ]
            id_field = meta["id_field"]
            quoted_index = quote_identifier(index)
            columns_sql = ", ".join(quote_identifier(n) for n in column_names)
            placeholders = ", ".join([ "?" ] * len(column_names) )
            insert_sql = f'INSERT INTO {quoted_index} ({columns_sql}) VALUES ({placeholders})'
            delete_sql = f'DELETE FROM {quoted_index} WHERE {quote_identifier(id_field)} = ?' if id_field else None

            affected_documents = 0
            deleted_documents  = 0

            try:
                await self.database.execute("BEGIN")

                for document in documents:
                    if id_field:
                        if id_field not in document:
                            raise ValueError(f"Document is missing required id field '{id_field}'.")
                        cursor = await self.database.execute(delete_sql, ( str(document[id_field]), ))
                        if cursor.rowcount and cursor.rowcount > 0:
                            deleted_documents += cursor.rowcount

                    values = [ serialize_value(document.get(name)) for name in column_names ]
                    await self.database.execute(insert_sql, values)
                    affected_documents += 1

                document_count = meta.get("document_count", 0) + affected_documents - deleted_documents
                await self.database.execute(
                    "UPDATE _search_meta SET document_count = ? WHERE index_name = ?",
                    ( document_count, index )
                )

                await self.database.commit()
            except BaseException:
                await self.database.rollback()
                raise

            meta["document_count"] = document_count

            return {
                "affected_documents": affected_documents,
                "total_documents": document_count,
            }

    async def _search(
        self,
        index: str,
        queries: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        index = validate_identifier(index, "index")

        meta = await self._load_meta(index)

        if meta is None:
            raise LookupError(f"Index '{index}' does not exist.")

        column_names = [ field["name"] for field in meta["fields"] ]
        quoted_index = quote_identifier(index)
        columns_sql = ", ".join(quote_identifier(name) for name in column_names)
        field_filter = ""

        if params.get("search_fields"):
            field_filter = "{" + " ".join(validate_identifier(field, "search field") for field in params["search_fields"]) + "} : "

        results: List[List[Dict[str, Any]]] = []

        for query in queries:
            async with self.database.execute(
                f'SELECT {columns_sql}, -bm25({quoted_index}) AS score '
                f'FROM {quoted_index} WHERE {quoted_index} MATCH ? '
                f'ORDER BY score DESC LIMIT ?',
                ( field_filter + escape_fts_term(query), params["limit"] )
            ) as cursor:
                rows = await cursor.fetchall()

            hits: List[Dict[str, Any]] = []
            for row in rows:
                document = { name: row[name] for name in column_names }
                hits.append({ "document": document, "score": row["score"] })

            results.append(hits)

        return results

    async def _delete(
        self,
        index: str,
        document_ids: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        index = validate_identifier(index, "index")

        async with self.write_lock:
            meta = await self._load_meta(index)

            if meta is None or not meta["id_field"]:
                return { "affected_documents": 0, "total_documents": meta["document_count"] if meta else 0 }

            quoted_index = quote_identifier(index)
            quoted_id_field = quote_identifier(meta["id_field"])
            affected_documents = 0

            try:
                await self.database.execute("BEGIN")

                for document_id in document_ids:
                    async with self.database.execute(
                        f'SELECT 1 FROM {quoted_index} WHERE {quoted_id_field} = ? LIMIT 1',
                        ( str(document_id), )
                    ) as cursor:
                        exists = await cursor.fetchone()

                    if exists is None:
                        continue

                    await self.database.execute(
                        f'DELETE FROM {quoted_index} WHERE {quoted_id_field} = ?',
                        ( str(document_id), )
                    )
                    affected_documents += 1

                document_count = max(0, meta.get("document_count", 0) - affected_documents)
                await self.database.execute(
                    "UPDATE _search_meta SET document_count = ? WHERE index_name = ?",
                    ( document_count, index )
                )

                await self.database.commit()
            except BaseException:
                await self.database.rollback()
                raise

            meta["document_count"] = document_count

            return { "affected_documents": affected_documents, "total_documents": document_count }

    async def _ensure_meta_table(self) -> None:
        await self.database.execute(
            "CREATE TABLE IF NOT EXISTS _search_meta ("
            "  index_name TEXT PRIMARY KEY,"
            "  fields_json TEXT NOT NULL,"
            "  id_field TEXT,"
            "  document_count INTEGER NOT NULL DEFAULT 0"
            ")"
        )

    async def _load_meta(self, index: str) -> Optional[Dict[str, Any]]:
        cached = self.meta_cache.get(index)

        if cached is not None:
            return cached

        async with self.database.execute(
            "SELECT fields_json, id_field, document_count FROM _search_meta WHERE index_name = ?",
            ( index, )
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        meta = {
            "fields": json.loads(row["fields_json"]),
            "id_field": row["id_field"],
            "document_count": row["document_count"] or 0,
        }
        self.meta_cache[index] = meta

        return meta

    async def _create_index(self, index: str, fields: List[Any]) -> Dict[str, Any]:
        id_field: Optional[str] = None
        field_defs: List[str] = []
        unindexed_fields: List[str] = []

        for field in fields:
            validate_identifier(field.name, "field")

            if field.type == SearchEngineFieldType.ID:
                if id_field is not None:
                    raise ValueError(f"Multiple ID fields defined: '{id_field}' and '{field.name}'. Only one is allowed.")
                id_field = field.name
                # ID fields are stored but excluded from full-text ranking.
                field_defs.append(f'{quote_identifier(field.name)} UNINDEXED')
                unindexed_fields.append(field.name)
            else:
                field_defs.append(quote_identifier(field.name))

        columns_sql = ", ".join(field_defs)
        # KEYWORD fields share the FTS5 column store with TEXT fields; the distinction
        # is preserved in _search_meta so higher-level logic can treat them differently
        # (e.g. filtered search by field name).
        await self.database.execute(
            f'CREATE VIRTUAL TABLE {quote_identifier(index)} USING fts5({columns_sql}, tokenize=\'unicode61\')'
        )

        fields_meta = [ { "name": f.name, "type": f.type.value } for f in fields ]
        await self.database.execute(
            "INSERT INTO _search_meta (index_name, fields_json, id_field, document_count) VALUES (?, ?, ?, 0)",
            ( index, json.dumps(fields_meta), id_field )
        )

        meta = { "fields": fields_meta, "id_field": id_field, "document_count": 0 }
        self.meta_cache[index] = meta

        return meta

@register_search_engine_service(SearchEngineDriver.SQLITE)
class SQLiteSearchEngineService(SearchEngineService):
    def __init__(self, id: str, config: SQLiteSearchEngineComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.database: Optional[aiosqlite.Connection] = None
        self.meta_cache: Dict[str, Any] = {}
        self.write_lock: asyncio.Lock = asyncio.Lock()

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "aiosqlite" ]

    async def _start(self) -> None:
        import aiosqlite

        database_path = os.path.join(os.path.expanduser(self.config.storage_dir), self.config.database)
        parent_dir = os.path.dirname(database_path)

        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        self.database = await aiosqlite.connect(database_path)
        self.database.row_factory = sqlite3.Row

        # WAL improves read/write concurrency for the single shared connection.
        await self.database.execute("PRAGMA journal_mode=WAL")
        await self.database.execute("PRAGMA synchronous=NORMAL")

        await super()._start()

    async def _stop(self) -> None:
        try:
            await super()._stop()
        finally:
            if self.database:
                try:
                    await self.database.close()
                finally:
                    self.database = None
                    self.meta_cache.clear()

    async def _run(self, action: SearchEngineActionConfig, context: ComponentActionContext) -> Any:
        return await SQLiteSearchEngineAction(action, self.database, self.meta_cache, self.write_lock).run(context)
