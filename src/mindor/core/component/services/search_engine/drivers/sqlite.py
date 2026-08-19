from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import SQLiteSearchEngineComponentConfig
from mindor.dsl.schema.action import SearchEngineActionConfig, SearchEngineFieldType
from mindor.core.foundation.cancellation import CancellationToken
from ..base import SearchEngineService, SearchEngineDriver, register_search_engine_service
from ..base import ComponentActionContext
from .common import SearchEngineAction
import sqlite3, os, json

if TYPE_CHECKING:
    import aiosqlite

class SQLiteSearchEngineAction(SearchEngineAction):
    async def _index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        fields = params["fields"]

        await self._ensure_meta_table()
        meta = await self._load_meta(index)

        if meta is None:
            if not fields:
                raise LookupError(f"Index '{index}' does not exist and no fields were provided.")

            meta = await self._create_index(index, fields)

        column_names = [ f["name"] for f in meta["fields"] ]
        placeholders = ", ".join([ "?" ] * len(column_names))
        columns_sql  = ", ".join(f'"{n}"' for n in column_names)
        insert_sql   = f'INSERT INTO "{index}" ({columns_sql}) VALUES ({placeholders})'

        affected_documents = 0

        for document in documents:
            if meta["id_field"] and meta["id_field"] in document:
                await self.database.execute(
                    f'DELETE FROM "{index}" WHERE "{meta["id_field"]}" = ?',
                    ( str(document[meta["id_field"]]), )
                )
            values = [ str(document.get(name, "")) for name in column_names ]
            await self.database.execute(insert_sql, values)
            affected_documents += 1

        await self.database.commit()

        async with self.database.execute(f'SELECT COUNT(*) AS c FROM "{index}"') as cursor:
            row = await cursor.fetchone()

        total_documents = row["c"]

        return { "affected_documents": affected_documents, "total_documents": total_documents }

    async def _search(
        self,
        index: str,
        queries: List[str],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        limit         = params["limit"]
        search_fields = params["search_fields"]

        meta = await self._load_meta(index)

        if meta is None:
            raise LookupError(f"Index '{index}' does not exist.")

        column_names = [ f["name"] for f in meta["fields"] ]
        columns_sql  = ", ".join(f'"{n}"' for n in column_names)

        results: List[List[Dict[str, Any]]] = []

        for query in queries:
            match_expr = ("{" + " ".join(search_fields) + "}: " + str(query)) if search_fields else str(query)

            async with self.database.execute(
                f'SELECT {columns_sql}, -bm25("{index}") AS score '
                f'FROM "{index}" WHERE "{index}" MATCH ? '
                f'ORDER BY score DESC LIMIT ?',
                ( match_expr, int(limit) )
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
        meta = await self._load_meta(index)

        if meta is None or not meta["id_field"]:
            return { "affected_documents": 0 }

        affected_documents = 0

        for document_id in document_ids:
            cursor = await self.database.execute(
                f'DELETE FROM "{index}" WHERE "{meta["id_field"]}" = ?',
                ( str(document_id), )
            )

            if cursor.rowcount > 0:
                affected_documents += cursor.rowcount

        await self.database.commit()

        return { "affected_documents": affected_documents }

    async def _ensure_meta_table(self) -> None:
        await self.database.execute(
            "CREATE TABLE IF NOT EXISTS _search_meta ("
            "  index_name TEXT PRIMARY KEY,"
            "  fields_json TEXT NOT NULL,"
            "  id_field TEXT"
            ")"
        )

    async def _load_meta(self, index: str) -> Optional[Dict[str, Any]]:
        async with self.database.execute(
            "SELECT fields_json, id_field FROM _search_meta WHERE index_name = ?",
            ( index, )
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return { "fields": json.loads(row["fields_json"]), "id_field": row["id_field"] }

    async def _create_index(self, index: str, fields: List[Any]) -> Dict[str, Any]:
        id_field: Optional[str] = None
        field_defs: List[str] = []

        for field in fields:
            if field.type == SearchEngineFieldType.ID and id_field is None:
                id_field = field.name
            # FTS5 stores every column as TEXT. The 'id'/'keyword'/'text' distinction is
            # preserved only in _search_meta and consulted at query/delete time.
            field_defs.append(field.name)

        columns_sql = ", ".join(field_defs)
        await self.database.execute(f"CREATE VIRTUAL TABLE \"{index}\" USING fts5({columns_sql}, tokenize='unicode61')")
        await self.database.execute(
            "INSERT INTO _search_meta (index_name, fields_json, id_field) VALUES (?, ?, ?)",
            ( index, json.dumps([ { "name": f.name, "type": f.type.value } for f in fields ]), id_field )
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
        return await SQLiteSearchEngineAction(action, self.database).run(context)
