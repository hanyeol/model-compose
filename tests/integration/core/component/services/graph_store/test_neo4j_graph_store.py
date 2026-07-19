"""
Integration tests for Neo4j graph store component against a real Neo4j instance.

Requires: Neo4j running on bolt://localhost:7687 with auth neo4j/testpassword
    docker run -d --name neo4j-test -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/testpassword neo4j:5
"""

import socket

import pytest
from neo4j import AsyncGraphDatabase
from pydantic import TypeAdapter

from unittest.mock import AsyncMock, MagicMock

from mindor.dsl.schema.action import Neo4jGraphStoreActionConfig
from mindor.dsl.schema.component import Neo4jGraphStoreComponentConfig
from mindor.core.component.services.graph_store.drivers.neo4j import (
    Neo4jGraphStoreAction,
    Neo4jGraphStoreService,
    Neo4jQueryBuilder,
)
from mindor.core.component.context import ComponentActionContext


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


NEO4J_URL = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testpassword"

ActionAdapter = TypeAdapter(Neo4jGraphStoreActionConfig)


def neo4j_is_available() -> bool:
    """Check if Neo4j bolt port is reachable."""
    try:
        with socket.create_connection(("localhost", 7687), timeout=2):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not neo4j_is_available(), reason="Neo4j is not available at bolt://localhost:7687")


@pytest.fixture
async def driver():
    """Provide an async Neo4j driver for tests."""
    drv = AsyncGraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
    yield drv
    await drv.close()


@pytest.fixture(autouse=True)
async def clean_db(driver):
    """Clean all data before each test."""
    async with driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    yield


@pytest.fixture
def ctx():
    """Create a mock ComponentActionContext with Pydantic model conversion."""
    context = MagicMock(spec=ComponentActionContext)
    context.cancellation_token = None

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


class TestInsertAndQuery:
    """Test inserting nodes and querying them back."""

    @pytest.mark.anyio
    async def test_insert_single_node(self, ctx, driver):
        """Verify a single node can be inserted and read back from the database."""
        config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "Person", "properties": {"name": "Alice", "age": 30}},
        })
        action = Neo4jGraphStoreAction(config)
        result = await action.run(ctx, driver, None)

        assert result["created_nodes"] == 1
        assert result["created_relationships"] == 0
        assert len(result["ids"]) == 1

        # Verify node exists in DB
        async with driver.session() as session:
            res = await session.run("MATCH (p:Person {name: 'Alice'}) RETURN p.name AS name, p.age AS age")
            records = await res.data()
            assert len(records) == 1
            assert records[0]["name"] == "Alice"
            assert records[0]["age"] == 30

    @pytest.mark.anyio
    async def test_insert_multiple_nodes(self, ctx, driver):
        """Verify multiple nodes can be inserted in a single action."""
        config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
                {"label": "Person", "properties": {"name": "Charlie"}},
            ],
        })
        action = Neo4jGraphStoreAction(config)
        result = await action.run(ctx, driver, None)

        assert result["created_nodes"] == 3
        assert len(result["ids"]) == 3

        async with driver.session() as session:
            res = await session.run("MATCH (p:Person) RETURN p.name AS name ORDER BY name")
            records = await res.data()
            names = [r["name"] for r in records]
            assert names == ["Alice", "Bob", "Charlie"]

    @pytest.mark.anyio
    async def test_query_with_params(self, ctx, driver):
        """Verify a parameterized query returns the correct results."""
        # Insert first
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice", "age": 30}},
                {"label": "Person", "properties": {"name": "Bob", "age": 25}},
            ],
        })
        await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)

        # Query with params
        query_config = ActionAdapter.validate_python({
            "method": "query",
            "query": "MATCH (p:Person {name: $name}) RETURN p.name AS name, p.age AS age",
            "params": {"name": "Alice"},
        })
        result = await Neo4jGraphStoreAction(query_config).run(ctx, driver, None)

        assert len(result) == 1
        assert result[0]["name"] == "Alice"
        assert result[0]["age"] == 30


class TestRelationships:
    """Test relationship operations."""

    @pytest.mark.anyio
    async def test_insert_relationship(self, ctx, driver):
        """Verify a relationship can be created between two existing nodes."""
        # Create two nodes
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id = insert_result["ids"]

        # Create relationship
        rel_config = ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {
                "type": "KNOWS",
                "from": alice_id,
                "to": bob_id,
                "properties": {"since": 2020},
            },
        })
        rel_result = await Neo4jGraphStoreAction(rel_config).run(ctx, driver, None)

        assert rel_result["created_relationships"] == 1
        assert len(rel_result["ids"]) == 1

        # Verify relationship
        async with driver.session() as session:
            res = await session.run(
                "MATCH (a:Person)-[r:KNOWS]->(b:Person) "
                "RETURN a.name AS from_name, b.name AS to_name, r.since AS since"
            )
            records = await res.data()
            assert len(records) == 1
            assert records[0]["from_name"] == "Alice"
            assert records[0]["to_name"] == "Bob"
            assert records[0]["since"] == 2020


class TestUpdate:
    """Test update operations."""

    @pytest.mark.anyio
    async def test_update_node_properties(self, ctx, driver):
        """Verify node properties can be updated after creation."""
        # Create node
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "Person", "properties": {"name": "Alice", "age": 30}},
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        node_id = insert_result["ids"][0]

        # Update
        update_config = ActionAdapter.validate_python({
            "method": "update",
            "node_id": node_id,
            "properties": {"age": 31, "city": "Seoul"},
        })
        update_result = await Neo4jGraphStoreAction(update_config).run(ctx, driver, None)
        assert update_result["affected_rows"] == 1

        # Verify
        async with driver.session() as session:
            res = await session.run("MATCH (p:Person {name: 'Alice'}) RETURN p.age AS age, p.city AS city")
            records = await res.data()
            assert records[0]["age"] == 31
            assert records[0]["city"] == "Seoul"

    @pytest.mark.anyio
    async def test_update_node_add_label(self, ctx, driver):
        """Verify additional labels can be added to a node."""
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "Person", "properties": {"name": "Alice"}},
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        node_id = insert_result["ids"][0]

        update_config = ActionAdapter.validate_python({
            "method": "update",
            "node_id": node_id,
            "labels": ["Employee"],
        })
        await Neo4jGraphStoreAction(update_config).run(ctx, driver, None)

        async with driver.session() as session:
            res = await session.run("MATCH (p:Person:Employee {name: 'Alice'}) RETURN p.name AS name")
            records = await res.data()
            assert len(records) == 1


class TestDelete:
    """Test delete operations."""

    @pytest.mark.anyio
    async def test_delete_node_detach(self, ctx, driver):
        """Verify deleting a node with detach also removes its relationships."""
        # Create nodes with relationship
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id = insert_result["ids"]

        rel_config = ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": alice_id, "to": bob_id},
        })
        await Neo4jGraphStoreAction(rel_config).run(ctx, driver, None)

        # Delete with detach
        delete_config = ActionAdapter.validate_python({
            "method": "delete",
            "node_id": alice_id,
            "detach": True,
        })
        delete_result = await Neo4jGraphStoreAction(delete_config).run(ctx, driver, None)
        assert delete_result["affected_rows"] == 1

        # Verify Alice deleted, Bob remains
        async with driver.session() as session:
            res = await session.run("MATCH (p:Person) RETURN p.name AS name")
            records = await res.data()
            assert len(records) == 1
            assert records[0]["name"] == "Bob"

    @pytest.mark.anyio
    async def test_delete_relationship(self, ctx, driver):
        """Verify deleting a relationship leaves both nodes intact."""
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id = insert_result["ids"]

        rel_config = ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": alice_id, "to": bob_id},
        })
        rel_result = await Neo4jGraphStoreAction(rel_config).run(ctx, driver, None)
        rel_id = rel_result["ids"][0]

        # Delete relationship only
        delete_config = ActionAdapter.validate_python({
            "method": "delete",
            "relationship_id": rel_id,
        })
        delete_result = await Neo4jGraphStoreAction(delete_config).run(ctx, driver, None)
        assert delete_result["affected_rows"] == 1

        # Both nodes should still exist
        async with driver.session() as session:
            res = await session.run("MATCH (p:Person) RETURN count(p) AS cnt")
            records = await res.data()
            assert records[0]["cnt"] == 2

            # No relationships
            res = await session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            records = await res.data()
            assert records[0]["cnt"] == 0


class TestTraverse:
    """Test graph traversal."""

    @pytest.mark.anyio
    async def test_traverse_outbound(self, ctx, driver):
        """Verify outbound traversal finds all reachable nodes within depth."""
        # Create a small graph: Alice -> Bob -> Charlie
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
                {"label": "Person", "properties": {"name": "Charlie"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id, charlie_id = insert_result["ids"]

        # Alice -> Bob
        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": alice_id, "to": bob_id},
        })).run(ctx, driver, None)

        # Bob -> Charlie
        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": bob_id, "to": charlie_id},
        })).run(ctx, driver, None)

        # Traverse from Alice outbound, depth 2
        traverse_config = ActionAdapter.validate_python({
            "method": "traverse",
            "start_node": alice_id,
            "direction": "out",
            "max_depth": 2,
            "relationship_types": ["KNOWS"],
        })
        result = await Neo4jGraphStoreAction(traverse_config).run(ctx, driver, None)

        names = {r["node"]["name"] for r in result}
        assert "Bob" in names
        assert "Charlie" in names
        assert "Alice" not in names

    @pytest.mark.anyio
    async def test_traverse_with_depth_limit(self, ctx, driver):
        """Verify traversal respects the max_depth limit."""
        # Alice -> Bob -> Charlie
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
                {"label": "Person", "properties": {"name": "Charlie"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id, charlie_id = insert_result["ids"]

        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": alice_id, "to": bob_id},
        })).run(ctx, driver, None)

        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": bob_id, "to": charlie_id},
        })).run(ctx, driver, None)

        # Traverse depth 1 only - should only find Bob
        traverse_config = ActionAdapter.validate_python({
            "method": "traverse",
            "start_node": alice_id,
            "direction": "out",
            "max_depth": 1,
            "relationship_types": ["KNOWS"],
        })
        result = await Neo4jGraphStoreAction(traverse_config).run(ctx, driver, None)

        names = {r["node"]["name"] for r in result}
        assert names == {"Bob"}

    @pytest.mark.anyio
    async def test_traverse_bidirectional(self, ctx, driver):
        """Verify bidirectional traversal finds nodes connected in both directions."""
        # Alice -> Bob, Charlie -> Bob
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
                {"label": "Person", "properties": {"name": "Charlie"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id, charlie_id = insert_result["ids"]

        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": alice_id, "to": bob_id},
        })).run(ctx, driver, None)

        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": charlie_id, "to": bob_id},
        })).run(ctx, driver, None)

        # Traverse from Bob bidirectionally
        traverse_config = ActionAdapter.validate_python({
            "method": "traverse",
            "start_node": bob_id,
            "direction": "both",
            "max_depth": 1,
        })
        result = await Neo4jGraphStoreAction(traverse_config).run(ctx, driver, None)

        names = {r["node"]["name"] for r in result}
        assert "Alice" in names
        assert "Charlie" in names

    @pytest.mark.anyio
    async def test_traverse_inbound(self, ctx, driver):
        """Verify inbound traversal finds nodes that point to the start node."""
        # Alice -> Bob, Charlie -> Bob
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
                {"label": "Person", "properties": {"name": "Charlie"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id, charlie_id = insert_result["ids"]

        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": alice_id, "to": bob_id},
        })).run(ctx, driver, None)

        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": charlie_id, "to": bob_id},
        })).run(ctx, driver, None)

        # Traverse inbound from Bob - should find Alice and Charlie
        traverse_config = ActionAdapter.validate_python({
            "method": "traverse",
            "start_node": bob_id,
            "direction": "in",
            "max_depth": 1,
        })
        result = await Neo4jGraphStoreAction(traverse_config).run(ctx, driver, None)

        names = {r["node"]["name"] for r in result}
        assert names == {"Alice", "Charlie"}

    @pytest.mark.anyio
    async def test_traverse_with_node_label_filter(self, ctx, driver):
        """Verify traversal can filter results by node label."""
        # Create Person and Company nodes
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
                {"label": "Company", "properties": {"name": "Acme"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id, acme_id = insert_result["ids"]

        # Alice -> Bob (KNOWS), Alice -> Acme (WORKS_AT)
        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "KNOWS", "from": alice_id, "to": bob_id},
        })).run(ctx, driver, None)

        await Neo4jGraphStoreAction(ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {"type": "WORKS_AT", "from": alice_id, "to": acme_id},
        })).run(ctx, driver, None)

        # Traverse from Alice, filter only Company nodes
        traverse_config = ActionAdapter.validate_python({
            "method": "traverse",
            "start_node": alice_id,
            "direction": "out",
            "max_depth": 1,
            "node_labels": ["Company"],
        })
        result = await Neo4jGraphStoreAction(traverse_config).run(ctx, driver, None)

        assert len(result) == 1
        assert result[0]["node"]["name"] == "Acme"


class TestUpdateRelationship:
    """Test relationship update operations."""

    @pytest.mark.anyio
    async def test_update_relationship_properties(self, ctx, driver):
        """Verify relationship properties can be updated after creation."""
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id = insert_result["ids"]

        rel_config = ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {
                "type": "KNOWS",
                "from": alice_id,
                "to": bob_id,
                "properties": {"since": 2020},
            },
        })
        rel_result = await Neo4jGraphStoreAction(rel_config).run(ctx, driver, None)
        rel_id = rel_result["ids"][0]

        # Update relationship properties
        update_config = ActionAdapter.validate_python({
            "method": "update",
            "relationship_id": rel_id,
            "properties": {"since": 2021, "strength": "strong"},
        })
        update_result = await Neo4jGraphStoreAction(update_config).run(ctx, driver, None)
        assert update_result["affected_rows"] == 1

        # Verify
        async with driver.session() as session:
            res = await session.run(
                "MATCH ()-[r:KNOWS]->() RETURN r.since AS since, r.strength AS strength"
            )
            records = await res.data()
            assert records[0]["since"] == 2021
            assert records[0]["strength"] == "strong"


class TestInsertRelationshipWithoutProperties:
    """Test inserting relationships without properties."""

    @pytest.mark.anyio
    async def test_insert_relationship_no_properties(self, ctx, driver):
        """Verify a relationship can be created without any properties."""
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id = insert_result["ids"]

        # Relationship without properties
        rel_config = ActionAdapter.validate_python({
            "method": "insert",
            "relationships": {
                "type": "KNOWS",
                "from": alice_id,
                "to": bob_id,
            },
        })
        rel_result = await Neo4jGraphStoreAction(rel_config).run(ctx, driver, None)

        assert rel_result["created_relationships"] == 1

        async with driver.session() as session:
            res = await session.run("MATCH ()-[r:KNOWS]->() RETURN count(r) AS cnt")
            records = await res.data()
            assert records[0]["cnt"] == 1


class TestQueryWithOutput:
    """Test query with output transform."""

    @pytest.mark.anyio
    async def test_query_with_output_transform(self, ctx, driver):
        """Verify query with output template triggers render_variable."""
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "Person", "properties": {"name": "Alice", "age": 30}},
        })
        await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)

        query_config = ActionAdapter.validate_python({
            "method": "query",
            "query": "MATCH (p:Person) RETURN p.name AS name",
            "output": "${result}",
        })
        await Neo4jGraphStoreAction(query_config).run(ctx, driver, None)

        # Verify render_variable was called with the output template
        ctx.render_variable.assert_any_call("${result}", ignore_files=True)


class TestDeleteMultiple:
    """Test deleting multiple nodes and relationships."""

    @pytest.mark.anyio
    async def test_delete_multiple_nodes(self, ctx, driver):
        """Verify multiple nodes can be deleted in a single action."""
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
                {"label": "Person", "properties": {"name": "Charlie"}},
            ],
        })
        insert_result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        alice_id, bob_id, _ = insert_result["ids"]

        # Delete two nodes at once
        delete_config = ActionAdapter.validate_python({
            "method": "delete",
            "node_id": [alice_id, bob_id],
            "detach": True,
        })
        delete_result = await Neo4jGraphStoreAction(delete_config).run(ctx, driver, None)
        assert delete_result["affected_rows"] == 2

        async with driver.session() as session:
            res = await session.run("MATCH (p:Person) RETURN p.name AS name")
            records = await res.data()
            assert len(records) == 1
            assert records[0]["name"] == "Charlie"


class TestQueryNoParams:
    """Test query without parameters."""

    @pytest.mark.anyio
    async def test_query_no_params(self, ctx, driver):
        """Verify a query without parameters returns correct results."""
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "Person", "properties": {"name": "Alice"}},
        })
        await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)

        query_config = ActionAdapter.validate_python({
            "method": "query",
            "query": "MATCH (p:Person) RETURN p.name AS name",
        })
        result = await Neo4jGraphStoreAction(query_config).run(ctx, driver, None)

        assert len(result) == 1
        assert result[0]["name"] == "Alice"


class TestQueryWithDatabase:
    """Test query with explicit database parameter."""

    @pytest.mark.anyio
    async def test_query_with_database(self, ctx, driver):
        """Verify an action can target a specific Neo4j database."""
        insert_config = ActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "Person", "properties": {"name": "Alice"}},
            "database": "neo4j",
        })
        result = await Neo4jGraphStoreAction(insert_config).run(ctx, driver, None)
        assert result["created_nodes"] == 1


class TestHelperFunctions:
    """Test internal helper functions directly."""

    def test_verify_identifier_valid(self):
        """Verify valid identifiers are accepted."""
        assert Neo4jQueryBuilder.verify_identifier("Person", "label") == "Person"
        assert Neo4jQueryBuilder.verify_identifier("_private", "label") == "_private"
        assert Neo4jQueryBuilder.verify_identifier("Name123", "label") == "Name123"

    def test_verify_identifier_invalid(self):
        """Verify invalid identifiers raise ValueError."""
        with pytest.raises(ValueError, match="Invalid label identifier"):
            Neo4jQueryBuilder.verify_identifier("123invalid", "label")
        with pytest.raises(ValueError, match="Invalid label identifier"):
            Neo4jQueryBuilder.verify_identifier("has space", "label")
        with pytest.raises(ValueError, match="Invalid label identifier"):
            Neo4jQueryBuilder.verify_identifier("has-dash", "label")

    def test_build_create_node_query(self):
        """Verify the generated CREATE node Cypher query structure."""
        cypher, params = Neo4jQueryBuilder.build_create_node("Person", {"name": "Alice", "age": 30})
        assert "CREATE (n:Person" in cypher
        assert "elementId(n) AS id" in cypher
        assert params == {"name": "Alice", "age": 30}

    def test_build_create_relationship_query_with_properties(self):
        """Verify the generated CREATE relationship Cypher includes properties."""
        cypher, params = Neo4jQueryBuilder.build_create_relationship(
            "KNOWS", "id1", "id2", {"since": 2020}
        )
        assert "KNOWS" in cypher
        assert params["from_id"] == "id1"
        assert params["to_id"] == "id2"
        assert params["prop_since"] == 2020

    def test_build_create_relationship_query_no_properties(self):
        """Verify the generated CREATE relationship Cypher works without properties."""
        cypher, params = Neo4jQueryBuilder.build_create_relationship("KNOWS", "id1", "id2", {})
        assert "KNOWS" in cypher
        assert "{" not in cypher.split("CREATE")[1].split("RETURN")[0] or "prop_" not in cypher

    def test_build_update_node_query_no_changes(self):
        """Verify that no update query is generated when there are no changes."""
        result = Neo4jQueryBuilder.build_update_node("id1", None, None)
        assert result is None

    def test_build_update_node_query_with_labels(self):
        """Verify the generated SET labels Cypher query structure."""
        result = Neo4jQueryBuilder.build_update_node("id1", None, ["Admin", "User"])
        assert result is not None
        cypher, params = result
        assert "SET n:Admin" in cypher
        assert "SET n:User" in cypher

    def test_build_update_relationship_query(self):
        """Verify the generated relationship update Cypher query structure."""
        cypher, params = Neo4jQueryBuilder.build_update_relationship("rid1", {"weight": 5})
        assert "r.weight = $prop_weight" in cypher
        assert params["prop_weight"] == 5

    def test_build_delete_node_query_detach(self):
        """Verify the generated DELETE node Cypher uses DETACH DELETE."""
        cypher, params = Neo4jQueryBuilder.build_delete_node("id1", True)
        assert "DETACH DELETE" in cypher
        assert params["id"] == "id1"

    def test_build_delete_node_query_no_detach(self):
        """Verify the generated DELETE node Cypher uses plain DELETE."""
        cypher, params = Neo4jQueryBuilder.build_delete_node("id1", False)
        assert "DETACH" not in cypher
        assert "DELETE n" in cypher

    def test_build_delete_relationship_query(self):
        """Verify the generated DELETE relationship Cypher query structure."""
        cypher, params = Neo4jQueryBuilder.build_delete_relationship("rid1")
        assert "DELETE r" in cypher
        assert params["id"] == "rid1"

    def test_build_traverse_query_outbound(self):
        """Verify the generated outbound traversal Cypher query structure."""
        cypher, params = Neo4jQueryBuilder.build_traverse("id1", "out", 3, ["KNOWS"], None)
        assert "->" in cypher
        assert "KNOWS" in cypher
        assert "*1..3" in cypher

    def test_build_traverse_query_inbound(self):
        """Verify the generated inbound traversal Cypher query structure."""
        cypher, params = Neo4jQueryBuilder.build_traverse("id1", "in", 2, None, None)
        assert "<-" in cypher
        assert "*1..2" in cypher

    def test_build_traverse_query_both(self):
        """Verify the generated bidirectional traversal Cypher has no directional arrows."""
        cypher, params = Neo4jQueryBuilder.build_traverse("id1", "both", 1, None, None)
        assert "->" not in cypher
        assert "<-" not in cypher

    def test_build_traverse_query_with_node_labels(self):
        """Verify the generated traversal Cypher includes node label filtering."""
        cypher, params = Neo4jQueryBuilder.build_traverse("id1", "out", 2, None, ["Person", "Company"])
        assert "labels(end)" in cypher
        assert "Person" in cypher
        assert "Company" in cypher


class TestServiceLifecycle:
    """Test Neo4jGraphStoreService lifecycle."""

    @pytest.mark.anyio
    async def test_service_serve_and_shutdown(self):
        """Verify the service can start, connect to Neo4j, and shut down cleanly."""
        config = Neo4jGraphStoreComponentConfig(
            type="graph-store",
            driver="neo4j",
            url=NEO4J_URL,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
        )
        service = Neo4jGraphStoreService("test-service", config, daemon=False)

        assert service.driver is None

        await service._start()
        assert service.driver is not None

        # Verify driver works
        async with service.driver.session() as session:
            result = await session.run("RETURN 1 AS n")
            records = await result.data()
            assert records[0]["n"] == 1

        await service._stop()
        assert service.driver is None

    def test_service_setup_requirements(self):
        """Verify the service reports its pip requirements."""
        config = Neo4jGraphStoreComponentConfig(
            type="graph-store",
            driver="neo4j",
            url=NEO4J_URL,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
        )
        service = Neo4jGraphStoreService("test-service", config, daemon=False)
        assert service.get_setup_requirements() == ["neo4j"]
