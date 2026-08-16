from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import SQLiteSearchEngineComponentConfig
from mindor.dsl.schema.action import SearchEngineActionConfig, SearchEngineFieldType
from ..base import SearchEngineService, SearchEngineDriver, register_search_engine_service
from ..base import ComponentActionContext
from .common import SearchEngineAction
import sqlite3, os, json

if TYPE_CHECKING:
    import aiosqlite

class SQLiteSearchEngineAction(SearchEngineAction):
    async def _index(self, database: aiosqlite.Connection, params: Dict[str, Any]) -> Dict[str, Any]:
        index_id  = params["index"]
        documents = params["documents"]

        await self._ensure_meta_table(database)
        meta = await self._load_meta(database, index_id)

        if meta is None:
            if not self.config.fields:
                raise LookupError(f"Index '{index_id}' does not exist and no fields were provided.")

            meta = await self._create_index(database, index_id, self.config.fields)

        column_names = [ f["name"] for f in meta["fields"] ]
        placeholders = ", ".join([ "?" ] * len(column_names))
        columns_sql  = ", ".join(f'"{n}"' for n in column_names)
        insert_sql   = f'INSERT INTO "{index_id}" ({columns_sql}) VALUES ({placeholders})'

        affected_documents = 0

        for document in documents:
            if meta["id_field"] and meta["id_field"] in document:
                await database.execute(
                    f'DELETE FROM "{index_id}" WHERE "{meta["id_field"]}" = ?',
                    ( str(document[meta["id_field"]]), )
                )
            values = [ str(document.get(name, "")) for name in column_names ]
            await database.execute(insert_sql, values)
            affected_documents += 1

        await database.commit()

        async with database.execute(f'SELECT COUNT(*) AS c FROM "{index_id}"') as cursor:
            row = await cursor.fetchone()

        total_documents = row["c"]

        return { "affected_documents": affected_documents, "total_documents": total_documents }

    async def _search(self, database: aiosqlite.Connection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        index_id      = params["index"]
        query         = params["query"]
        limit         = params["limit"]
        search_fields = params["search_fields"]

        meta = await self._load_meta(database, index_id)

        if meta is None:
            raise LookupError(f"Index '{index_id}' does not exist.")

        match_expr = ("{" + " ".join(search_fields) + "}: " + str(query)) if search_fields else str(query)

        column_names = [ f["name"] for f in meta["fields"] ]
        columns_sql  = ", ".join(f'"{n}"' for n in column_names)

        async with database.execute(
            f'SELECT {columns_sql}, -bm25("{index_id}") AS score '
            f'FROM "{index_id}" WHERE "{index_id}" MATCH ? '
            f'ORDER BY score DESC LIMIT ?',
            ( match_expr, int(limit) )
        ) as cursor:
            rows = await cursor.fetchall()

        results: List[Dict[str, Any]] = []

        for row in rows:
            document = { name: row[name] for name in column_names }
            results.append({ "document": document, "score": row["score"] })

        return results

    async def _delete(self, database: aiosqlite.Connection, params: Dict[str, Any]) -> Dict[str, Any]:
        index_id     = params["index"]
        document_ids = params["document_ids"]

        meta = await self._load_meta(database, index_id)

        if meta is None or not meta["id_field"]:
            return { "affected_documents": 0 }

        affected_documents = 0

        for document_id in document_ids:
            cursor = await database.execute(
                f'DELETE FROM "{index_id}" WHERE "{meta["id_field"]}" = ?',
                ( str(document_id), )
            )

            if cursor.rowcount > 0:
                affected_documents += cursor.rowcount

        await database.commit()

        return { "affected_documents": affected_documents }

    async def _ensure_meta_table(self, database: aiosqlite.Connection) -> None:
        await database.execute(
            "CREATE TABLE IF NOT EXISTS _search_meta ("
            "  index_name TEXT PRIMARY KEY,"
            "  fields_json TEXT NOT NULL,"
            "  id_field TEXT"
            ")"
        )

    async def _load_meta(self, database: aiosqlite.Connection, index_id: str) -> Optional[Dict[str, Any]]:
        async with database.execute(
            "SELECT fields_json, id_field FROM _search_meta WHERE index_name = ?",
            ( index_id, )
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return { "fields": json.loads(row["fields_json"]), "id_field": row["id_field"] }

    async def _create_index(self, database: aiosqlite.Connection, index_id: str, fields: List[Any]) -> Dict[str, Any]:
        id_field: Optional[str] = None
        field_defs: List[str] = []

        for field in fields:
            if field.type == SearchEngineFieldType.ID and id_field is None:
                id_field = field.name
            # FTS5 stores every column as TEXT. The 'id'/'keyword'/'text' distinction is
            # preserved only in _search_meta and consulted at query/delete time.
            field_defs.append(field.name)

        columns_sql = ", ".join(field_defs)
        await database.execute(f"CREATE VIRTUAL TABLE \"{index_id}\" USING fts5({columns_sql}, tokenize='unicode61')")
        await database.execute(
            "INSERT INTO _search_meta (index_name, fields_json, id_field) VALUES (?, ?, ?)",
            ( index_id, json.dumps([ { "name": f.name, "type": f.type.value } for f in fields ]), id_field )
        )

        return { "fields": [ { "name": f.name, "type": f.type.value } for f in fields ], "id_field": id_field }

@register_search_engine_service(SearchEngineDriver.SQLITE)
class SQLiteSearchEngineService(SearchEngineService):
    def __init__(self, id: str, config: SQLiteSearchEngineComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.database: Optional[aiosqlite.Connection] = None

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

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.database:
            await self.database.close()
            self.database = None

    async def _run(self, action: SearchEngineActionConfig, context: ComponentActionContext) -> Any:
        return await SQLiteSearchEngineAction(action).run(context, self.database)
