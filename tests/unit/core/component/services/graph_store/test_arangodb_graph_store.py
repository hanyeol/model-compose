"""Unit tests for ArangoDB graph store action execution with mocked drivers."""

import pytest
from pydantic import TypeAdapter

from unittest.mock import AsyncMock, MagicMock, patch

from mindor.dsl.schema.action import (
    ArangoDBGraphStoreActionConfig,
    ArangoDBGraphQueryActionConfig,
    ArangoDBGraphInsertActionConfig,
    ArangoDBGraphUpdateActionConfig,
    ArangoDBGraphDeleteActionConfig,
    ArangoDBGraphTraverseActionConfig,
)
from mindor.core.component.services.graph_store.drivers.arangodb import (
    ArangoDBGraphStoreAction,
)
from mindor.core.component.context import ComponentActionContext


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture
def mock_context():
    """Create a mock ComponentActionContext with Pydantic model conversion."""
    context = MagicMock(spec=ComponentActionContext)

    def _convert(value):
        from pydantic import BaseModel
        if isinstance(value, BaseModel):
            return value.model_dump(by_alias=True)
        if isinstance(value, list):
            return [_convert(v) for v in value]
        if isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        return value

    async def render_variable(value, ignore_files=False):
        return _convert(value)

    context.render_variable = AsyncMock(side_effect=render_variable)
    context.register_source = MagicMock()
    context.contains_variable_reference = MagicMock(return_value=False)
    return context


@pytest.fixture
def mock_db():
    """Create a mock ArangoDB database client."""
    db = MagicMock()
    db.has_collection = MagicMock(return_value=True)
    db.collection = MagicMock(return_value=MagicMock())
    db.aql = MagicMock()
    return db


ActionAdapter = TypeAdapter(ArangoDBGraphStoreActionConfig)


class TestArangoDBQueryAction:
    """Test ArangoDB query action execution."""

    @pytest.mark.anyio
    async def test_query_basic(self, mock_context, mock_db):
        """Test that a basic AQL query returns results and registers them."""
        mock_cursor = iter([{"name": "Alice"}, {"name": "Bob"}])
        mock_db.aql.execute = MagicMock(return_value=mock_cursor)

        config = ActionAdapter.validate_python({
            "method": "query",
            "query": "FOR p IN persons RETURN p",
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        mock_db.aql.execute.assert_called_once_with(
            "FOR p IN persons RETURN p", bind_vars={}
        )
        assert result == [{"name": "Alice"}, {"name": "Bob"}]
        mock_context.register_source.assert_called_once_with("result", result)

    @pytest.mark.anyio
    async def test_query_with_params(self, mock_context, mock_db):
        """Test that query parameters are forwarded as bind_vars."""
        mock_cursor = iter([{"name": "Alice"}])
        mock_db.aql.execute = MagicMock(return_value=mock_cursor)

        config = ActionAdapter.validate_python({
            "method": "query",
            "query": "FOR p IN persons FILTER p.name == @name RETURN p",
            "params": {"name": "Alice"},
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        await action.run(mock_context)

        mock_db.aql.execute.assert_called_once_with(
            "FOR p IN persons FILTER p.name == @name RETURN p",
            bind_vars={"name": "Alice"},
        )

    @pytest.mark.anyio
    async def test_query_with_output_transform(self, mock_context, mock_db):
        """Test that the output template triggers render_variable."""
        mock_cursor = iter([{"name": "Alice"}])
        mock_db.aql.execute = MagicMock(return_value=mock_cursor)

        config = ActionAdapter.validate_python({
            "method": "query",
            "query": "FOR p IN persons RETURN p",
            "output": "${result[0]}",
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        await action.run(mock_context)

        mock_context.render_variable.assert_any_call("${result[0]}")


class TestArangoDBInsertAction:
    """Test ArangoDB insert action execution."""

    @pytest.mark.anyio
    async def test_insert_single_node(self, mock_context, mock_db):
        """Test that inserting a single node returns correct creation summary."""
        mock_collection = MagicMock()
        mock_collection.insert = MagicMock(return_value={"_id": "persons/1", "_key": "1"})
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "insert",
            "collection": "persons",
            "nodes": {"label": "persons", "properties": {"name": "Alice", "age": 30}},
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["created_nodes"] == 1
        assert result["created_relationships"] == 0
        assert result["ids"] == ["persons/1"]
        mock_collection.insert.assert_called_once()

    @pytest.mark.anyio
    async def test_insert_multiple_nodes(self, mock_context, mock_db):
        """Test that inserting multiple nodes returns all created IDs."""
        mock_collection = MagicMock()
        mock_collection.insert = MagicMock(side_effect=[
            {"_id": "persons/1", "_key": "1"},
            {"_id": "persons/2", "_key": "2"},
        ])
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "persons", "properties": {"name": "Alice"}},
                {"label": "persons", "properties": {"name": "Bob"}},
            ],
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["created_nodes"] == 2
        assert result["ids"] == ["persons/1", "persons/2"]
        assert mock_collection.insert.call_count == 2

    @pytest.mark.anyio
    async def test_insert_relationship(self, mock_context, mock_db):
        """Test that inserting a relationship returns correct creation summary."""
        mock_collection = MagicMock()
        mock_collection.insert = MagicMock(return_value={"_id": "friendships/1", "_key": "1"})
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "insert",
            "edge_collection": "friendships",
            "relationships": {
                "type": "friendships",
                "from": "persons/1",
                "to": "persons/2",
                "properties": {"since": 2020},
            },
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["created_relationships"] == 1
        assert result["created_nodes"] == 0
        assert result["ids"] == ["friendships/1"]
        insert_call = mock_collection.insert.call_args[0][0]
        assert insert_call["_from"] == "persons/1"
        assert insert_call["_to"] == "persons/2"
        assert insert_call["since"] == 2020

    @pytest.mark.anyio
    async def test_insert_node_with_id(self, mock_context, mock_db):
        """Test that inserting a node with an explicit ID uses it as _key."""
        mock_collection = MagicMock()
        mock_collection.insert = MagicMock(return_value={"_id": "persons/alice", "_key": "alice"})
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "persons", "id": "alice", "properties": {"name": "Alice"}},
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        await action.run(mock_context)

        insert_call = mock_collection.insert.call_args[0][0]
        assert insert_call["_key"] == "alice"

    @pytest.mark.anyio
    async def test_insert_creates_collection_if_missing(self, mock_context, mock_db):
        """Test that inserting into a missing collection creates it first."""
        mock_db.has_collection = MagicMock(return_value=False)
        mock_collection = MagicMock()
        mock_collection.insert = MagicMock(return_value={"_id": "new_collection/1", "_key": "1"})
        mock_db.collection = MagicMock(return_value=mock_collection)
        mock_db.create_collection = MagicMock()

        config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "new_collection", "properties": {"name": "Alice"}},
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        await action.run(mock_context)

        mock_db.create_collection.assert_called_once_with("new_collection")


class TestArangoDBUpdateAction:
    """Test ArangoDB update action execution."""

    @pytest.mark.anyio
    async def test_update_node_with_full_id(self, mock_context, mock_db):
        """Test that updating a node with a full ID extracts collection and key."""
        mock_collection = MagicMock()
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "update",
            "node_id": "persons/12345",
            "properties": {"age": 31},
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["affected_rows"] == 1
        mock_db.collection.assert_called_with("persons")
        update_call = mock_collection.update.call_args[0][0]
        assert update_call["_key"] == "12345"
        assert update_call["age"] == 31

    @pytest.mark.anyio
    async def test_update_node_with_collection_field(self, mock_context, mock_db):
        """Test that updating a node uses the explicit collection field."""
        mock_collection = MagicMock()
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "update",
            "collection": "persons",
            "node_id": "12345",
            "properties": {"age": 31},
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["affected_rows"] == 1
        mock_db.collection.assert_called_with("persons")

    @pytest.mark.anyio
    async def test_update_multiple_nodes(self, mock_context, mock_db):
        """Test that updating multiple nodes applies changes to each one."""
        mock_collection = MagicMock()
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "update",
            "collection": "persons",
            "node_id": ["12345", "67890"],
            "properties": {"status": "active"},
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["affected_rows"] == 2
        assert mock_collection.update.call_count == 2


class TestArangoDBDeleteAction:
    """Test ArangoDB delete action execution."""

    @pytest.mark.anyio
    async def test_delete_node_with_full_id(self, mock_context, mock_db):
        """Test that deleting a node with a full ID extracts collection and key."""
        mock_collection = MagicMock()
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "delete",
            "node_id": "persons/12345",
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["affected_rows"] == 1
        mock_db.collection.assert_called_with("persons")
        mock_collection.delete.assert_called_once_with("12345")

    @pytest.mark.anyio
    async def test_delete_multiple_nodes(self, mock_context, mock_db):
        """Test that deleting multiple nodes removes each one."""
        mock_collection = MagicMock()
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "delete",
            "collection": "persons",
            "node_id": ["12345", "67890"],
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["affected_rows"] == 2
        assert mock_collection.delete.call_count == 2

    @pytest.mark.anyio
    async def test_delete_relationship(self, mock_context, mock_db):
        """Test that deleting a relationship removes it from the edge collection."""
        mock_collection = MagicMock()
        mock_db.collection = MagicMock(return_value=mock_collection)

        config = ActionAdapter.validate_python({
            "method": "delete",
            "relationship_id": "friendships/abc123",
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        assert result["affected_rows"] == 1
        mock_db.collection.assert_called_with("friendships")
        mock_collection.delete.assert_called_once_with("abc123")


class TestArangoDBTraverseAction:
    """Test ArangoDB traverse action execution."""

    @pytest.mark.anyio
    async def test_traverse_with_graph(self, mock_context, mock_db):
        """Test that graph-based traversal uses the graph API correctly."""
        mock_graph = MagicMock()
        mock_graph.traverse = MagicMock(return_value={
            "vertices": [
                {"_id": "persons/1", "name": "Alice"},
                {"_id": "persons/2", "name": "Bob"},
            ],
            "paths": [],
        })
        mock_db.graph = MagicMock(return_value=mock_graph)

        config = ActionAdapter.validate_python({
            "method": "traverse",
            "start_node": "persons/1",
            "graph": "social_graph",
            "direction": "out",
            "max_depth": 2,
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        mock_db.graph.assert_called_once_with("social_graph")
        mock_graph.traverse.assert_called_once_with(
            start_vertex="persons/1",
            direction="outbound",
            max_depth=2,
        )
        assert len(result) == 1
        assert result[0]["node"]["name"] == "Bob"

    @pytest.mark.anyio
    async def test_traverse_with_edge_collection(self, mock_context, mock_db):
        """Test that edge-collection-based traversal uses AQL correctly."""
        mock_cursor = iter([
            {"node": {"name": "Bob"}, "edge": {"_from": "persons/1", "_to": "persons/2"}, "depth": 1},
        ])
        mock_db.aql.execute = MagicMock(return_value=mock_cursor)

        config = ActionAdapter.validate_python({
            "method": "traverse",
            "start_node": "persons/1",
            "edge_collection": "friendships",
            "direction": "both",
            "max_depth": 3,
        })
        action = ArangoDBGraphStoreAction(config, mock_db)
        result = await action.run(mock_context)

        mock_db.aql.execute.assert_called_once()
        aql = mock_db.aql.execute.call_args[0][0]
        assert "ANY" in aql
        assert "friendships" in aql
        assert len(result) == 1

    @pytest.mark.anyio
    async def test_traverse_direction_mapping(self, mock_context, mock_db):
        """Test that direction values are correctly mapped to ArangoDB terms."""
        mock_graph = MagicMock()
        mock_graph.traverse = MagicMock(return_value={"vertices": [], "paths": []})
        mock_db.graph = MagicMock(return_value=mock_graph)

        directions = [("out", "outbound"), ("in", "inbound"), ("both", "any")]
        for input_dir, expected_dir in directions:
            config = ActionAdapter.validate_python({
                "method": "traverse",
                "start_node": "persons/1",
                "graph": "g",
                "direction": input_dir,
            })
            action = ArangoDBGraphStoreAction(config, mock_db)
            await action.run(mock_context)

            call_kwargs = mock_graph.traverse.call_args[1]
            assert call_kwargs["direction"] == expected_dir, (
                f"Expected '{expected_dir}' for direction='{input_dir}', got '{call_kwargs['direction']}'"
            )
