"""Integration tests for the SQLite search-engine driver against a real SQLite FTS5 database."""

import os

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
        result = await SQLiteSearchEngineAction(config).run(context, nested_path)

        assert os.path.exists(nested_path)
        assert result["indexed"] == 1
        assert result["total"] == 1

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
        await SQLiteSearchEngineAction(index_config).run(context, database_path)

        search_config = SQLiteSearchSearchActionConfig(
            method="search",
            index="docs",
            query="Python",
        )
        result = await SQLiteSearchEngineAction(search_config).run(context, database_path)

        assert result["count"] == 1
        assert result["hits"][0]["title"] == "Python tutorial"
        assert result["hits"][0]["score"] > 0

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
        await SQLiteSearchEngineAction(index_config).run(context, database_path)

        search_config = SQLiteSearchSearchActionConfig(
            method="search",
            index="docs",
            query="apple",
        )
        result = await SQLiteSearchEngineAction(search_config).run(context, database_path)

        assert result["count"] == 2
        # Descending score: triple-apple doc should outrank single-apple doc.
        assert result["hits"][0]["score"] >= result["hits"][1]["score"]
        assert result["hits"][0]["content"] == "apple apple apple"

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
        await SQLiteSearchEngineAction(index_config).run(context, database_path)

        # Search restricted to `title` should match only the first document.
        search_config = SQLiteSearchSearchActionConfig(
            method="search",
            index="docs",
            query="pizza",
            search_fields=["title"],
        )
        result = await SQLiteSearchEngineAction(search_config).run(context, database_path)

        assert result["count"] == 1
        assert result["hits"][0]["title"] == "pizza recipe"

    @pytest.mark.anyio
    async def test_search_respects_limit(self, database_path, context):
        """SEARCH never returns more than `limit` hits."""
        index_config = SQLiteSearchIndexActionConfig(
            method="index",
            index="docs",
            fields=[{ "name": "content", "type": "text" }],
            documents=[{ "content": f"keyword doc {i}" } for i in range(10)],
        )
        await SQLiteSearchEngineAction(index_config).run(context, database_path)

        search_config = SQLiteSearchSearchActionConfig(
            method="search",
            index="docs",
            query="keyword",
            limit=3,
        )
        result = await SQLiteSearchEngineAction(search_config).run(context, database_path)

        assert result["count"] == 3
        assert len(result["hits"]) == 3

    @pytest.mark.anyio
    async def test_index_upserts_on_id_collision(self, database_path, context):
        """Re-indexing a document with the same id replaces the previous one."""
        fields = [
            { "name": "document_id",  "type": "id" },
            { "name": "content", "type": "text" },
        ]

        await SQLiteSearchEngineAction(
            SQLiteSearchIndexActionConfig(
                method="index", index="docs", fields=fields,
                documents=[{ "document_id": "1", "content": "first version" }],
            )
        ).run(context, database_path)

        await SQLiteSearchEngineAction(
            SQLiteSearchIndexActionConfig(
                method="index", index="docs",
                documents=[{ "document_id": "1", "content": "second version" }],
            )
        ).run(context, database_path)

        result = await SQLiteSearchEngineAction(
            SQLiteSearchSearchActionConfig(method="search", index="docs", query="version")
        ).run(context, database_path)

        assert result["count"] == 1
        assert result["hits"][0]["content"] == "second version"

    @pytest.mark.anyio
    async def test_delete_removes_documents(self, database_path, context):
        """DELETE removes documents and reports the affected count."""
        fields = [
            { "name": "document_id",  "type": "id" },
            { "name": "content", "type": "text" },
        ]
        await SQLiteSearchEngineAction(
            SQLiteSearchIndexActionConfig(
                method="index", index="docs", fields=fields,
                documents=[
                    { "document_id": "1", "content": "alpha" },
                    { "document_id": "2", "content": "beta" },
                    { "document_id": "3", "content": "gamma" },
                ],
            )
        ).run(context, database_path)

        delete_result = await SQLiteSearchEngineAction(
            SQLiteSearchDeleteActionConfig(method="delete", index="docs", document_ids=["1", "3"])
        ).run(context, database_path)
        assert delete_result["deleted"] == 2

        # Only document_id=2 should remain searchable.
        search_result = await SQLiteSearchEngineAction(
            SQLiteSearchSearchActionConfig(method="search", index="docs", query="alpha OR beta OR gamma")
        ).run(context, database_path)
        contents = [hit["content"] for hit in search_result["hits"]]
        assert contents == ["beta"]

    @pytest.mark.anyio
    async def test_search_raises_when_database_missing(self, tmp_path, context):
        """SEARCH raises FileNotFoundError and does not create the database file."""
        missing_path = str(tmp_path / "never-created.db")

        config = SQLiteSearchSearchActionConfig(method="search", index="docs", query="x")

        with pytest.raises(FileNotFoundError, match="does not exist"):
            await SQLiteSearchEngineAction(config).run(context, missing_path)

        assert not os.path.exists(missing_path)

    @pytest.mark.anyio
    async def test_delete_raises_when_database_missing(self, tmp_path, context):
        """DELETE raises FileNotFoundError and does not create the database file."""
        missing_path = str(tmp_path / "never-created.db")

        config = SQLiteSearchDeleteActionConfig(method="delete", index="docs", document_ids=["1"])

        with pytest.raises(FileNotFoundError, match="does not exist"):
            await SQLiteSearchEngineAction(config).run(context, missing_path)

        assert not os.path.exists(missing_path)

    @pytest.mark.anyio
    async def test_search_raises_when_index_missing(self, database_path, context):
        """SEARCH raises ValueError when the requested index does not exist in the DB."""
        # Bootstrap the DB by indexing into a different index first.
        await SQLiteSearchEngineAction(
            SQLiteSearchIndexActionConfig(
                method="index", index="other",
                fields=[{ "name": "content", "type": "text" }],
                documents=[{ "content": "hi" }],
            )
        ).run(context, database_path)

        config = SQLiteSearchSearchActionConfig(method="search", index="missing", query="x")
        with pytest.raises(ValueError, match="Index 'missing' does not exist"):
            await SQLiteSearchEngineAction(config).run(context, database_path)

    @pytest.mark.anyio
    async def test_index_raises_when_index_missing_and_no_fields(self, database_path, context):
        """INDEX without `fields` on a new index raises a clear ValueError."""
        config = SQLiteSearchIndexActionConfig(
            method="index", index="docs",
            documents=[{ "title": "hello" }],
        )
        with pytest.raises(ValueError, match="no fields were provided"):
            await SQLiteSearchEngineAction(config).run(context, database_path)

    @pytest.mark.anyio
    async def test_index_can_append_to_existing_index_without_fields(self, database_path, context):
        """INDEX without `fields` on an existing index reuses the stored schema."""
        # Create the index with schema.
        await SQLiteSearchEngineAction(
            SQLiteSearchIndexActionConfig(
                method="index", index="docs",
                fields=[{ "name": "content", "type": "text" }],
                documents=[{ "content": "first" }],
            )
        ).run(context, database_path)

        # Append without re-declaring fields.
        result = await SQLiteSearchEngineAction(
            SQLiteSearchIndexActionConfig(
                method="index", index="docs",
                documents=[{ "content": "second" }],
            )
        ).run(context, database_path)

        assert result["indexed"] == 1
        assert result["total"] == 2

    @pytest.mark.anyio
    async def test_multiple_indexes_in_same_database(self, database_path, context):
        """Multiple indexes live independently as separate FTS5 virtual tables in one DB file."""
        await SQLiteSearchEngineAction(
            SQLiteSearchIndexActionConfig(
                method="index", index="articles",
                fields=[{ "name": "body", "type": "text" }],
                documents=[{ "body": "article one" }],
            )
        ).run(context, database_path)

        await SQLiteSearchEngineAction(
            SQLiteSearchIndexActionConfig(
                method="index", index="comments",
                fields=[{ "name": "body", "type": "text" }],
                documents=[{ "body": "comment one" }],
            )
        ).run(context, database_path)

        articles = await SQLiteSearchEngineAction(
            SQLiteSearchSearchActionConfig(method="search", index="articles", query="article")
        ).run(context, database_path)
        comments = await SQLiteSearchEngineAction(
            SQLiteSearchSearchActionConfig(method="search", index="comments", query="comment")
        ).run(context, database_path)

        assert articles["count"] == 1 and articles["hits"][0]["body"] == "article one"
        assert comments["count"] == 1 and comments["hits"][0]["body"] == "comment one"
