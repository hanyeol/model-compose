"""Unit tests for Neo4j graph store action execution with mocked drivers."""

import asyncio

import pytest
from pydantic import TypeAdapter

from unittest.mock import AsyncMock, MagicMock, patch

from mindor.dsl.schema.action import (
    Neo4jGraphStoreActionConfig,
    Neo4jGraphQueryActionConfig,
    Neo4jGraphInsertActionConfig,
    Neo4jGraphUpdateActionConfig,
    Neo4jGraphDeleteActionConfig,
    Neo4jGraphTraverseActionConfig,
)
from mindor.core.component.services.graph_store.drivers.neo4j import (
    Neo4jGraphStoreAction,
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
    return context


ActionAdapter = TypeAdapter(Neo4jGraphStoreActionConfig)


class TestNeo4jQueryAction:
    """Test Neo4j query action execution."""

    @pytest.mark.anyio
    async def test_query_basic(self, mock_context):
        """Verify a basic Cypher query returns results and registers them."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": {"name": "Alice"}}])
        mock_session.run = AsyncMock(return_value=mock_result)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "query",
            "query": "MATCH (n:Person) RETURN n",
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        result = await action.run(mock_context, asyncio.get_running_loop())

        mock_session.run.assert_called_once_with(
            "MATCH (n:Person) RETURN n", parameters={}
        )
        assert result == [{"n": {"name": "Alice"}}]
        mock_context.register_source.assert_called_once_with("result", [{"n": {"name": "Alice"}}])

    @pytest.mark.anyio
    async def test_query_with_params(self, mock_context):
        """Verify that query parameters are forwarded to the Cypher call."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "query",
            "query": "MATCH (n:Person {name: $name}) RETURN n",
            "params": {"name": "Alice"},
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        await action.run(mock_context, asyncio.get_running_loop())

        mock_session.run.assert_called_once_with(
            "MATCH (n:Person {name: $name}) RETURN n",
            parameters={"name": "Alice"},
        )

    @pytest.mark.anyio
    async def test_query_with_output_transform(self, mock_context):
        """Verify that the output template triggers render_variable."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": {"name": "Alice"}}])
        mock_session.run = AsyncMock(return_value=mock_result)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "query",
            "query": "MATCH (n) RETURN n",
            "output": "${result[0]}",
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        await action.run(mock_context, asyncio.get_running_loop())

        mock_context.render_variable.assert_any_call("${result[0]}")


class TestNeo4jInsertAction:
    """Test Neo4j insert action execution."""

    @staticmethod
    def mock_run_result(element_id):
        """Create a mock session.run result that returns a single record with the given element ID."""
        mock_result = AsyncMock()
        mock_record = {"id": element_id}
        mock_result.single = AsyncMock(return_value=mock_record)
        return mock_result

    @pytest.mark.anyio
    async def test_insert_single_node(self, mock_context):
        """Verify inserting a single node returns the correct creation summary."""
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=self.mock_run_result("4:abc:1"))

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "Person", "properties": {"name": "Alice", "age": 30}},
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert result["created_nodes"] == 1
        assert result["created_relationships"] == 0
        assert result["ids"] == ["4:abc:1"]
        mock_session.run.assert_called_once()

    @pytest.mark.anyio
    async def test_insert_multiple_nodes(self, mock_context):
        """Verify inserting multiple nodes returns all created IDs."""
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(side_effect=[
            self.mock_run_result("4:abc:1"),
            self.mock_run_result("4:abc:2"),
        ])

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
            ],
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert result["created_nodes"] == 2
        assert result["ids"] == ["4:abc:1", "4:abc:2"]
        assert mock_session.run.call_count == 2

    @pytest.mark.anyio
    async def test_insert_relationship(self, mock_context):
        """Verify inserting a relationship returns the correct creation summary."""
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=self.mock_run_result("5:abc:1"))

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {
                "type": "KNOWS",
                "from": "4:abc:1",
                "to": "4:abc:2",
                "properties": {"since": 2020},
            },
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert result["created_relationships"] == 1
        assert result["created_nodes"] == 0
        assert result["ids"] == ["5:abc:1"]


class TestNeo4jDeleteAction:
    """Test Neo4j delete action execution."""

    @pytest.mark.anyio
    async def test_delete_node_with_detach(self, mock_context):
        """Verify deleting a node with detach uses DETACH DELETE in the Cypher query."""
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=AsyncMock())

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "delete",
            "node_id": "4:abc:123",
            "detach": True,
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        result = await action.run(mock_context, asyncio.get_running_loop())

        assert result["affected_rows"] == 1
        call_args = mock_session.run.call_args
        assert "DETACH DELETE" in call_args[0][0]

    @pytest.mark.anyio
    async def test_delete_node_without_detach(self, mock_context):
        """Verify deleting a node without detach uses plain DELETE."""
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=AsyncMock())

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "delete",
            "node_id": "4:abc:123",
            "detach": False,
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        result = await action.run(mock_context, asyncio.get_running_loop())

        call_args = mock_session.run.call_args
        assert "DETACH DELETE" not in call_args[0][0]
        assert "DELETE n" in call_args[0][0]


class TestNeo4jTraverseAction:
    """Test Neo4j traverse action execution."""

    @pytest.mark.anyio
    async def test_traverse_outbound(self, mock_context):
        """Verify outbound traversal generates correct Cypher with direction and depth."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[
            {"node": {"name": "Bob"}, "depth": 1, "relationship_types": ["KNOWS"]},
        ])
        mock_session.run = AsyncMock(return_value=mock_result)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        config = ActionAdapter.validate_python({
            "method": "traverse",
            "start_node": "4:abc:123",
            "direction": "out",
            "max_depth": 2,
            "relationship_types": ["KNOWS"],
        })
        action = Neo4jGraphStoreAction(config, mock_session)
        result = await action.run(mock_context, asyncio.get_running_loop())

        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "KNOWS" in cypher
        assert "*1..2" in cypher
        assert "->" in cypher
        assert len(result) == 1
