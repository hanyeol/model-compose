from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import SQLiteSearchEngineComponentConfig
from mindor.dsl.schema.action import SearchEngineActionConfig, SQLiteSearchEngineActionConfig, SearchEngineActionMethod, SearchEngineFieldType
from ..base import SearchEngineService, SearchEngineDriver, register_search_engine_service
from ..base import ComponentActionContext
import os
import sqlite3
import json

class SQLiteSearchEngineAction:
    def __init__(self, config: SQLiteSearchEngineActionConfig):
        self.config: SQLiteSearchEngineActionConfig = config

    async def run(self, context: ComponentActionContext, database_path: str) -> Any:
        result = await self._dispatch(context, database_path)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, convert_media=False)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext, database_path: str) -> Dict[str, Any]:
        if self.config.method == SearchEngineActionMethod.INDEX:
            return await self._index(context, database_path)

        if self.config.method == SearchEngineActionMethod.SEARCH:
            return await self._search(context, database_path)

        if self.config.method == SearchEngineActionMethod.DELETE:
            return await self._delete(context, database_path)

        raise ValueError(f"Unsupported search engine action method: {self.config.method}")

    async def _index(self, context: ComponentActionContext, database_path: str) -> Dict[str, Any]:
        index_name = await context.render_variable(self.config.index)
        documents  = await context.render_variable(self.config.documents)

        parent_dir = os.path.dirname(database_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        database = sqlite3.connect(database_path)
        database.row_factory = sqlite3.Row
        try:
            self._ensure_meta_table(database)
            meta = self._load_meta(database, index_name)

            if meta is None:
                if not self.config.fields:
                    raise LookupError(f"Index '{index_name}' does not exist and no fields were provided.")
                meta = self._create_index(database, index_name, self.config.fields)

            column_names = [ f["name"] for f in meta["fields"] ]
            placeholders = ", ".join([ "?" ] * len(column_names))
            columns_sql  = ", ".join(f'"{n}"' for n in column_names)
            insert_sql   = f'INSERT INTO "{index_name}" ({columns_sql}) VALUES ({placeholders})'

            indexed = 0
            for document in documents:
                if meta["id_field"] and meta["id_field"] in document:
                    database.execute(
                        f'DELETE FROM "{index_name}" WHERE "{meta["id_field"]}" = ?',
                        ( str(document[meta["id_field"]]), )
                    )
                values = [ str(document.get(name, "")) for name in column_names ]
                database.execute(insert_sql, values)
                indexed += 1
            database.commit()

            total = database.execute(f'SELECT COUNT(*) AS c FROM "{index_name}"').fetchone()["c"]
        finally:
            database.close()

        context.register_source("indexed", indexed)
        context.register_source("total", total)

        return { "indexed": indexed, "total": total }

    async def _search(self, context: ComponentActionContext, database_path: str) -> Dict[str, Any]:
        index_name    = await context.render_variable(self.config.index)
        query         = await context.render_variable(self.config.query)
        limit         = await context.render_variable(self.config.limit)
        search_fields = await context.render_variable(self.config.search_fields)

        if not os.path.exists(database_path):
            raise FileNotFoundError(f"Search engine database does not exist: {database_path}. Run an 'index' action first to create the database.")

        database = sqlite3.connect(database_path)
        database.row_factory = sqlite3.Row
        try:
            meta = self._load_meta(database, index_name)
            if meta is None:
                raise LookupError(f"Index '{index_name}' does not exist.")

            match_expr = ("{" + " ".join(search_fields) + "}: " + str(query)) if search_fields else str(query)

            column_names = [ f["name"] for f in meta["fields"] ]
            columns_sql  = ", ".join(f'"{n}"' for n in column_names)

            # bm25() returns a non-positive score where lower means more relevant.
            # Negate so that higher score == more relevant for consumers of the result.
            rows = database.execute(
                f'SELECT {columns_sql}, -bm25("{index_name}") AS score '
                f'FROM "{index_name}" WHERE "{index_name}" MATCH ? '
                f'ORDER BY score DESC LIMIT ?',
                ( match_expr, int(limit) )
            ).fetchall()

            hits: List[Dict[str, Any]] = []
            for row in rows:
                hit = { name: row[name] for name in column_names }
                hit["score"] = row["score"]
                hits.append(hit)
        finally:
            database.close()

        context.register_source("hits", hits)
        context.register_source("count", len(hits))

        return { "hits": hits, "count": len(hits) }

    async def _delete(self, context: ComponentActionContext, database_path: str) -> Dict[str, Any]:
        index_name   = await context.render_variable(self.config.index)
        document_ids = await context.render_variable(self.config.document_ids)

        if not os.path.exists(database_path):
            raise FileNotFoundError(f"Search engine database does not exist: {database_path}. Run an 'index' action first to create the database.")

        database = sqlite3.connect(database_path)
        database.row_factory = sqlite3.Row
        try:
            meta = self._load_meta(database, index_name)
            if meta is None or not meta["id_field"]:
                deleted = 0
            else:
                deleted = 0
                for document_id in document_ids:
                    cursor = database.execute(
                        f'DELETE FROM "{index_name}" WHERE "{meta["id_field"]}" = ?',
                        ( str(document_id), )
                    )
                    if cursor.rowcount > 0:
                        deleted += cursor.rowcount
                database.commit()
        finally:
            database.close()

        context.register_source("deleted", deleted)

        return { "deleted": deleted }

    def _ensure_meta_table(self, database: sqlite3.Connection) -> None:
        database.execute(
            "CREATE TABLE IF NOT EXISTS _search_meta ("
            "  index_name TEXT PRIMARY KEY,"
            "  fields_json TEXT NOT NULL,"
            "  id_field TEXT"
            ")"
        )

    def _load_meta(self, database: sqlite3.Connection, index_name: str) -> Optional[Dict[str, Any]]:
        row = database.execute(
            "SELECT fields_json, id_field FROM _search_meta WHERE index_name = ?",
            ( index_name, )
        ).fetchone()

        if row is None:
            return None

        return { "fields": json.loads(row["fields_json"]), "id_field": row["id_field"] }

    def _create_index(self, database: sqlite3.Connection, index_name: str, fields: List[Any]) -> Dict[str, Any]:
        id_field: Optional[str] = None
        field_defs: List[str] = []

        for field in fields:
            if field.type == SearchEngineFieldType.ID and id_field is None:
                id_field = field.name
            # FTS5 stores every column as TEXT. The 'id'/'keyword'/'text' distinction is
            # preserved only in _search_meta and consulted at query/delete time.
            field_defs.append(field.name)

        columns_sql = ", ".join(field_defs)
        database.execute(f"CREATE VIRTUAL TABLE \"{index_name}\" USING fts5({columns_sql}, tokenize='unicode61')")
        database.execute(
            "INSERT INTO _search_meta (index_name, fields_json, id_field) VALUES (?, ?, ?)",
            ( index_name, json.dumps([ { "name": f.name, "type": f.type.value } for f in fields ]), id_field )
        )

        return { "fields": [ { "name": f.name, "type": f.type.value } for f in fields ], "id_field": id_field }

@register_search_engine_service(SearchEngineDriver.SQLITE)
class SQLiteSearchEngineService(SearchEngineService):
    def __init__(self, id: str, config: SQLiteSearchEngineComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _run(self, action: SearchEngineActionConfig, context: ComponentActionContext) -> Any:
        async def _run():
            database_path = os.path.join(self.config.storage_dir, self.config.database)
            return await SQLiteSearchEngineAction(action).run(context, database_path)

        return await self.run_in_thread(_run)
