"""Tests for search-engine component and action schemas (SQLite)."""

import pytest
from pydantic import ValidationError, TypeAdapter

from mindor.dsl.schema.component import (
    ComponentConfig,
    SearchEngineComponentConfig,
    SQLiteSearchEngineComponentConfig,
    SearchEngineDriver,
)
from mindor.dsl.schema.action import (
    SearchEngineActionConfig,
    SQLiteSearchEngineActionConfig,
    SearchEngineActionMethod,
    SearchEngineFieldType,
    SearchEngineFieldConfig,
    SQLiteSearchIndexActionConfig,
    SQLiteSearchSearchActionConfig,
    SQLiteSearchDeleteActionConfig,
)


ComponentAdapter = TypeAdapter(ComponentConfig)
SQLiteActionAdapter = TypeAdapter(SQLiteSearchEngineActionConfig)


# ──────────────────────────────────────────────
# Component Schema Tests
# ──────────────────────────────────────────────


class TestSearchEngineComponentSchema:
    """Test search-engine component schema validation."""

    def test_minimal_sqlite_config(self):
        """Test minimal SQLite configuration with defaults."""
        config = ComponentAdapter.validate_python({
            "id": "search",
            "type": "search-engine",
            "driver": "sqlite",
            "actions": [],
        })
        assert config.type.value == "search-engine"
        assert config.driver == SearchEngineDriver.SQLITE
        assert config.storage_dir == "./sqlite-search"
        assert config.database == "search.db"
        assert config.actions == []

    def test_full_sqlite_config(self):
        """Test SQLite configuration with all options set."""
        config = ComponentAdapter.validate_python({
            "id": "knowledge-base",
            "type": "search-engine",
            "driver": "sqlite",
            "storage_dir": "./data/search",
            "database": "knowledge.db",
            "actions": [{
                "method": "index",
                "index": "knowledge",
                "fields": [
                    { "name": "document_id",  "type": "id" },
                    { "name": "title",   "type": "text" },
                    { "name": "content", "type": "text" },
                ],
                "documents": [{ "document_id": "1", "title": "t", "content": "c" }],
            }],
        })
        assert isinstance(config, SQLiteSearchEngineComponentConfig)
        assert config.storage_dir == "./data/search"
        assert config.database == "knowledge.db"
        assert len(config.actions) == 1
        assert isinstance(config.actions[0], SQLiteSearchIndexActionConfig)

    def test_driver_field_is_required(self):
        """Driver must be specified explicitly."""
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "search",
                "type": "search-engine",
                "actions": [],
            })

    def test_unknown_driver_rejected(self):
        """Unknown driver values are rejected by the discriminated union."""
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "search",
                "type": "search-engine",
                "driver": "elasticsearch",
                "actions": [],
            })


# ──────────────────────────────────────────────
# Action Schema Tests
# ──────────────────────────────────────────────


class TestSQLiteSearchEngineActionSchema:
    """Test SQLite search-engine action discrimination by `method`."""

    def test_index_action(self):
        config = SQLiteActionAdapter.validate_python({
            "method": "index",
            "index": "docs",
            "fields": [{ "name": "title", "type": "text" }],
            "documents": [{ "title": "hello" }],
        })
        assert isinstance(config, SQLiteSearchIndexActionConfig)
        assert config.method == SearchEngineActionMethod.INDEX
        assert config.fields[0].type == SearchEngineFieldType.TEXT

    def test_search_action_defaults(self):
        config = SQLiteActionAdapter.validate_python({
            "method": "search",
            "index": "docs",
            "query": "hello",
        })
        assert isinstance(config, SQLiteSearchSearchActionConfig)
        assert config.method == SearchEngineActionMethod.SEARCH
        assert config.limit == 10
        assert config.search_fields is None

    def test_search_action_with_overrides(self):
        config = SQLiteActionAdapter.validate_python({
            "method": "search",
            "index": "docs",
            "query": "hello",
            "search_fields": ["title", "body"],
            "limit": 25,
        })
        assert config.search_fields == ["title", "body"]
        assert config.limit == 25

    def test_delete_action(self):
        config = SQLiteActionAdapter.validate_python({
            "method": "delete",
            "index": "docs",
            "document_ids": ["a", "b"],
        })
        assert isinstance(config, SQLiteSearchDeleteActionConfig)
        assert config.document_ids == ["a", "b"]

    def test_unknown_method_rejected(self):
        with pytest.raises(ValidationError):
            SQLiteActionAdapter.validate_python({
                "method": "upsert",
                "index": "docs",
                "documents": [],
            })

    def test_field_type_defaults_to_text(self):
        """When `type` is omitted on a field, it defaults to text."""
        config = SQLiteActionAdapter.validate_python({
            "method": "index",
            "index": "docs",
            "fields": [{ "name": "body" }],
            "documents": [],
        })
        assert config.fields[0].type == SearchEngineFieldType.TEXT
