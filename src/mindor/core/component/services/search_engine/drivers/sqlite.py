from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import SQLiteSearchEngineComponentConfig
from mindor.dsl.schema.action import SearchEngineActionConfig, SearchEngineActionMethod, SearchEngineFieldType
from ..base import SearchEngineService, SearchEngineDriver, register_search_engine_service
from ..base import ComponentActionContext
from .common import SearchEngineAction
import sqlite3, os, json

class SQLiteSearchEngineAction(SearchEngineAction):
    async def _index(self, database: sqlite3.Connection, context: ComponentActionContext) -> Dict[str, Any]:
        index_id  = await context.render_variable(self.config.index)
        documents = await context.render_variable(self.config.documents)

        if documents is None:
            raise ValueError("'documents' must be specified for 'index' method")

        self._ensure_meta_table(database)
        meta = self._load_meta(database, index_id)

        if meta is None:
            if not self.config.fields:
                raise LookupError(f"Index '{index_id}' does not exist and no fields were provided.")
            meta = self._create_index(database, index_id, self.config.fields)

        column_names = [ f["name"] for f in meta["fields"] ]
        placeholders = ", ".join([ "?" ] * len(column_names))
        columns_sql  = ", ".join(f'"{n}"' for n in column_names)
        insert_sql   = f'INSERT INTO "{index_id}" ({columns_sql}) VALUES ({placeholders})'

        affected_documents = 0
        for document in documents:
            if meta["id_field"] and meta["id_field"] in document:
                database.execute(
                    f'DELETE FROM "{index_id}" WHERE "{meta["id_field"]}" = ?',
                    ( str(document[meta["id_field"]]), )
                )
            values = [ str(document.get(name, "")) for name in column_names ]
            database.execute(insert_sql, values)
            affected_documents += 1
        database.commit()

        total_documents = database.execute(f'SELECT COUNT(*) AS c FROM "{index_id}"').fetchone()["c"]

        return { "affected_documents": affected_documents, "total_documents": total_documents }

    async def _search(self, database: sqlite3.Connection, context: ComponentActionContext) -> List[Dict[str, Any]]:
        index_id      = await context.render_variable(self.config.index)
        query         = await context.render_variable(self.config.query)
        limit         = await context.render_variable(self.config.limit)
        search_fields = await context.render_variable(self.config.search_fields)

        if query is None:
            raise ValueError("'query' must be specified for 'search' method")

        meta = self._load_meta(database, index_id)
        if meta is None:
            raise LookupError(f"Index '{index_id}' does not exist.")

        match_expr = ("{" + " ".join(search_fields) + "}: " + str(query)) if search_fields else str(query)

        column_names = [ f["name"] for f in meta["fields"] ]
        columns_sql  = ", ".join(f'"{n}"' for n in column_names)

        rows = database.execute(
            f'SELECT {columns_sql}, -bm25("{index_id}") AS score '
            f'FROM "{index_id}" WHERE "{index_id}" MATCH ? '
            f'ORDER BY score DESC LIMIT ?',
            ( match_expr, int(limit) )
        ).fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            document = { name: row[name] for name in column_names }
            results.append({ "document": document, "score": row["score"] })

        return results

    async def _delete(self, database: sqlite3.Connection, context: ComponentActionContext) -> Dict[str, Any]:
        index_id     = await context.render_variable(self.config.index)
        document_ids = await context.render_variable(self.config.document_ids)

        if document_ids is None:
            raise ValueError("'document_ids' must be specified for 'delete' method")

        meta = self._load_meta(database, index_id)
        if meta is None or not meta["id_field"]:
            return { "affected_documents": 0 }

        affected_documents = 0
        for document_id in document_ids:
            cursor = database.execute(
                f'DELETE FROM "{index_id}" WHERE "{meta["id_field"]}" = ?',
                ( str(document_id), )
            )
            if cursor.rowcount > 0:
                affected_documents += cursor.rowcount
        database.commit()

        return { "affected_documents": affected_documents }

    def _ensure_meta_table(self, database: sqlite3.Connection) -> None:
        database.execute(
            "CREATE TABLE IF NOT EXISTS _search_meta ("
            "  index_name TEXT PRIMARY KEY,"
            "  fields_json TEXT NOT NULL,"
            "  id_field TEXT"
            ")"
        )

    def _load_meta(self, database: sqlite3.Connection, index_id: str) -> Optional[Dict[str, Any]]:
        row = database.execute(
            "SELECT fields_json, id_field FROM _search_meta WHERE index_name = ?",
            ( index_id, )
        ).fetchone()

        if row is None:
            return None

        return { "fields": json.loads(row["fields_json"]), "id_field": row["id_field"] }

    def _create_index(self, database: sqlite3.Connection, index_id: str, fields: List[Any]) -> Dict[str, Any]:
        id_field: Optional[str] = None
        field_defs: List[str] = []

        for field in fields:
            if field.type == SearchEngineFieldType.ID and id_field is None:
                id_field = field.name
            # FTS5 stores every column as TEXT. The 'id'/'keyword'/'text' distinction is
            # preserved only in _search_meta and consulted at query/delete time.
            field_defs.append(field.name)

        columns_sql = ", ".join(field_defs)
        database.execute(f"CREATE VIRTUAL TABLE \"{index_id}\" USING fts5({columns_sql}, tokenize='unicode61')")
        database.execute(
            "INSERT INTO _search_meta (index_name, fields_json, id_field) VALUES (?, ?, ?)",
            ( index_id, json.dumps([ { "name": f.name, "type": f.type.value } for f in fields ]), id_field )
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

            if action.method != SearchEngineActionMethod.INDEX and not os.path.exists(database_path):
                raise FileNotFoundError(f"Search engine database does not exist: {database_path}. Run an 'index' action first to create the database.")

            parent_dir = os.path.dirname(database_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            database = sqlite3.connect(database_path)
            database.row_factory = sqlite3.Row
            try:
                return await SQLiteSearchEngineAction(action).run(database, context)
            finally:
                database.close()

        return await self.run_in_thread(_run)
