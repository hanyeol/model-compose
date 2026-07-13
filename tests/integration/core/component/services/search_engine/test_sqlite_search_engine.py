"""Integration tests for the SQLite search-engine driver against a real SQLite FTS5 database."""

import asyncio
import os
import sqlite3

import pytest

from mindor.dsl.schema.action import (
    SQLiteSearchIndexActionConfig,
    SQLiteSearchSearchActionConfig,
    SQLiteSearchDeleteActionConfig,
)
from mindor.core.component.services.search_engine.drivers.sqlite import SQLiteSearchEngineAction
from mindor.core.component.context import ComponentActionContext


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture
def database_path(tmp_path):
    """Provide a fresh, isolated SQLite database file path for each test."""
    return str(tmp_path / "search.db")


@pytest.fixture
def context():
    """Provide a real ComponentActionContext."""
    return ComponentActionContext(run_id="test-run", input={})



def _connect(path: str) -> sqlite3.Connection:
    """Mirror SQLiteSearchEngineService: open a connection with row_factory and ensure parent dir."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    database = sqlite3.connect(path)
    database.row_factory = sqlite3.Row
    return database


async def _run_action(action_config, path: str, context):
    """Open a SQLite connection, dispatch, and close — mirrors SQLiteSearchEngineService._run.

    Mirrors the production check that non-INDEX methods must run against an existing DB.
    """
    from mindor.dsl.schema.action import SearchEngineActionMethod
    if action_config.method != SearchEngineActionMethod.INDEX and not os.path.exists(path):
        raise FileNotFoundError(f"Search engine database does not exist: {path}. Run an 'index' action first to create the database.")
    database = _connect(path)
    try:
        return await SQLiteSearchEngineAction(action_config).run(context, asyncio.get_running_loop(), database)
    finally:
        database.close()


class TestSQLiteSearchEngineIntegration:
    """End-to-end behavior of INDEX, SEARCH, and DELETE against a real SQLite FTS5 DB."""

    @pytest.mark.anyio
    async def test_index_creates_database_and_directory(self, tmp_path, context):
        """INDEX creates the parent directory and the .db file on first use."""
        nested_path = str(tmp_path / "deep" / "nested" / "search.db")

        config = SQLiteSearchIndexActionConfig(
            method="index",
            index="docs",
            fields=[{ "name": "title", "type": "text" }],
            documents=[{ "title": "hello" }],
        )
        result = await _run_action(config, nested_path, context)

        assert os.path.exists(nested_path)
        assert result["affected_documents"] == 1
        assert result["total_documents"] == 1

    @pytest.mark.anyio
    async def test_index_then_search_returns_documents(self, database_path, context):
        """Documents inserted via INDEX are retrievable via SEARCH."""
        index_config = SQLiteSearchIndexActionConfig(
            method="index",
            index="docs",
            fields=[
                { "name": "title",   "type": "text" },
                { "name": "content", "type": "text" },
            ],
            documents=[
                { "title": "Python tutorial",  "content": "Learn Python basics" },
                { "title": "JavaScript guide", "content": "Modern JavaScript features" },
                { "title": "Rust handbook",    "content": "Systems programming in Rust" },
            ],
        )
        await _run_action(index_config, database_path, context)

        search_config = SQLiteSearchSearchActionConfig(
            method="search",
            index="docs",
            query="Python",
        )
        result = await _run_action(search_config, database_path, context)

        assert len(result) == 1
        assert result[0]["document"]["title"] == "Python tutorial"
        assert result[0]["score"] > 0

    @pytest.mark.anyio
    async def test_search_orders_by_relevance(self, database_path, context):
        """SEARCH returns hits ordered by descending BM25 score."""
        index_config = SQLiteSearchIndexActionConfig(
            method="index",
            index="docs",
            fields=[{ "name": "content", "type": "text" }],
            documents=[
                { "content": "apple apple apple" },
                { "content": "apple banana" },
                { "content": "banana cherry" },
            ],
        )
        await _run_action(index_config, database_path, context)

        search_config = SQLiteSearchSearchActionConfig(
            method="search",
            index="docs",
            query="apple",
        )
        result = await _run_action(search_config, database_path, context)

        assert len(result) == 2
        # Descending score: triple-apple doc should outrank single-apple doc.
        assert result[0]["score"] >= result[1]["score"]
        assert result[0]["document"]["content"] == "apple apple apple"

    @pytest.mark.anyio
    async def test_search_with_field_filter(self, database_path, context):
        """search_fields restricts MATCH to the specified columns only."""
        index_config = SQLiteSearchIndexActionConfig(
            method="index",
            index="docs",
            fields=[
                { "name": "title", "type": "text" },
                { "name": "body",  "type": "text" },
            ],
            documents=[
                { "title": "pizza recipe", "body": "tomato cheese" },
                { "title": "salad bowl",   "body": "pizza topping idea" },
            ],
        )
        await _run_action(index_config, database_path, context)

        # Search restricted to `title` should match only the first document.
        search_config = SQLiteSearchSearchActionConfig(
            method="search",
            index="docs",
            query="pizza",
            search_fields=["title"],
        )
        result = await _run_action(search_config, database_path, context)

        assert len(result) == 1
        assert result[0]["document"]["title"] == "pizza recipe"

    @pytest.mark.anyio
    async def test_search_respects_limit(self, database_path, context):
        """SEARCH never returns more than `limit` hits."""
        index_config = SQLiteSearchIndexActionConfig(
            method="index",
            index="docs",
            fields=[{ "name": "content", "type": "text" }],
            documents=[{ "content": f"keyword doc {i}" } for i in range(10)],
        )
        await _run_action(index_config, database_path, context)

        search_config = SQLiteSearchSearchActionConfig(
            method="search",
            index="docs",
            query="keyword",
            limit=3,
        )
        result = await _run_action(search_config, database_path, context)

        assert len(result) == 3
        assert len(result) == 3

    @pytest.mark.anyio
    async def test_index_upserts_on_id_collision(self, database_path, context):
        """Re-indexing a document with the same id replaces the previous one."""
        fields = [
            { "name": "document_id",  "type": "id" },
            { "name": "content", "type": "text" },
        ]

        await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="docs", fields=fields,
                documents=[{ "document_id": "1", "content": "first version" }],
            ), database_path, context)

        await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="docs",
                documents=[{ "document_id": "1", "content": "second version" }],
            ), database_path, context)

        result = await _run_action(SQLiteSearchSearchActionConfig(method="search", index="docs", query="version"), database_path, context)

        assert len(result) == 1
        assert result[0]["document"]["content"] == "second version"

    @pytest.mark.anyio
    async def test_delete_removes_documents(self, database_path, context):
        """DELETE removes documents and reports the affected count."""
        fields = [
            { "name": "document_id",  "type": "id" },
            { "name": "content", "type": "text" },
        ]
        await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="docs", fields=fields,
                documents=[
                    { "document_id": "1", "content": "alpha" },
                    { "document_id": "2", "content": "beta" },
                    { "document_id": "3", "content": "gamma" },
                ],
            ), database_path, context)

        delete_result = await _run_action(SQLiteSearchDeleteActionConfig(method="delete", index="docs", document_ids=["1", "3"]), database_path, context)
        assert delete_result["affected_documents"] == 2

        # Only document_id=2 should remain searchable.
        search_result = await _run_action(SQLiteSearchSearchActionConfig(method="search", index="docs", query="alpha OR beta OR gamma"), database_path, context)
        contents = [hit["document"]["content"] for hit in search_result]
        assert contents == ["beta"]

    @pytest.mark.anyio
    async def test_search_raises_when_database_missing(self, tmp_path, context):
        """SEARCH raises FileNotFoundError and does not create the database file."""
        missing_path = str(tmp_path / "never-created.db")

        config = SQLiteSearchSearchActionConfig(method="search", index="docs", query="x")

        with pytest.raises(FileNotFoundError, match="does not exist"):
            await _run_action(config, missing_path, context)

        assert not os.path.exists(missing_path)

    @pytest.mark.anyio
    async def test_delete_raises_when_database_missing(self, tmp_path, context):
        """DELETE raises FileNotFoundError and does not create the database file."""
        missing_path = str(tmp_path / "never-created.db")

        config = SQLiteSearchDeleteActionConfig(method="delete", index="docs", document_ids=["1"])

        with pytest.raises(FileNotFoundError, match="does not exist"):
            await _run_action(config, missing_path, context)

        assert not os.path.exists(missing_path)

    @pytest.mark.anyio
    async def test_search_raises_when_index_missing(self, database_path, context):
        """SEARCH raises ValueError when the requested index does not exist in the DB."""
        # Bootstrap the DB by indexing into a different index first.
        await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="other",
                fields=[{ "name": "content", "type": "text" }],
                documents=[{ "content": "hi" }],
            ), database_path, context)

        config = SQLiteSearchSearchActionConfig(method="search", index="missing", query="x")
        with pytest.raises(LookupError, match="Index 'missing' does not exist"):
            await _run_action(config, database_path, context)

    @pytest.mark.anyio
    async def test_index_raises_when_index_missing_and_no_fields(self, database_path, context):
        """INDEX without `fields` on a new index raises a clear ValueError."""
        config = SQLiteSearchIndexActionConfig(
            method="index", index="docs",
            documents=[{ "title": "hello" }],
        )
        with pytest.raises(LookupError, match="no fields were provided"):
            await _run_action(config, database_path, context)

    @pytest.mark.anyio
    async def test_index_can_append_to_existing_index_without_fields(self, database_path, context):
        """INDEX without `fields` on an existing index reuses the stored schema."""
        # Create the index with schema.
        await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="docs",
                fields=[{ "name": "content", "type": "text" }],
                documents=[{ "content": "first" }],
            ), database_path, context)

        # Append without re-declaring fields.
        result = await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="docs",
                documents=[{ "content": "second" }],
            ), database_path, context)

        assert result["affected_documents"] == 1
        assert result["total_documents"] == 2

    @pytest.mark.anyio
    async def test_multiple_indexes_in_same_database(self, database_path, context):
        """Multiple indexes live independently as separate FTS5 virtual tables in one DB file."""
        await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="articles",
                fields=[{ "name": "body", "type": "text" }],
                documents=[{ "body": "article one" }],
            ), database_path, context)

        await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="comments",
                fields=[{ "name": "body", "type": "text" }],
                documents=[{ "body": "comment one" }],
            ), database_path, context)

        articles = await _run_action(SQLiteSearchSearchActionConfig(method="search", index="articles", query="article"), database_path, context)
        comments = await _run_action(SQLiteSearchSearchActionConfig(method="search", index="comments", query="comment"), database_path, context)

        assert len(articles) == 1 and articles[0]["document"]["body"] == "article one"
        assert len(comments) == 1 and comments[0]["document"]["body"] == "comment one"


class TestSQLiteSearchEngineSearchIO:
    """I/O matrix for the SEARCH method: single result / stream output."""

    async def _seed_index(self, context, database_path):
        await _run_action(SQLiteSearchIndexActionConfig(
                method="index", index="docs",
                fields=[
                    { "name": "title",   "type": "text" },
                    { "name": "content", "type": "text" },
                ],
                documents=[
                    { "title": "Python tutorial",  "content": "Learn Python basics" },
                    { "title": "JavaScript guide", "content": "Modern JavaScript features" },
                    { "title": "Rust handbook",    "content": "Systems programming in Rust" },
                ],
            ), database_path, context)

    @pytest.mark.anyio
    async def test_single_query_returns_list_of_hits(self, database_path, context):
        await self._seed_index(context, database_path)

        config = SQLiteSearchSearchActionConfig(method="search", index="docs", query="Python")
        result = await _run_action(config, database_path, context)

        assert isinstance(result, list)
        assert len(result) >= 1
        assert "document" in result[0] and "score" in result[0]
