import pytest
from pydantic import ValidationError, TypeAdapter

from mindor.dsl.schema.component import (
    ComponentConfig,
    GraphStoreComponentConfig,
    Neo4jGraphStoreComponentConfig,
    ArangoDBGraphStoreComponentConfig,
    GraphStoreDriver,
)
from mindor.dsl.schema.action import (
    GraphStoreActionConfig,
    Neo4jGraphStoreActionConfig,
    ArangoDBGraphStoreActionConfig,
    GraphStoreActionMethod,
    Neo4jGraphQueryActionConfig,
    Neo4jGraphInsertActionConfig,
    Neo4jGraphUpdateActionConfig,
    Neo4jGraphDeleteActionConfig,
    Neo4jGraphTraverseActionConfig,
    ArangoDBGraphQueryActionConfig,
    ArangoDBGraphInsertActionConfig,
    ArangoDBGraphUpdateActionConfig,
    ArangoDBGraphDeleteActionConfig,
    ArangoDBGraphTraverseActionConfig,
)


ComponentAdapter = TypeAdapter(ComponentConfig)
Neo4jActionAdapter = TypeAdapter(Neo4jGraphStoreActionConfig)
ArangoDBActionAdapter = TypeAdapter(ArangoDBGraphStoreActionConfig)


# ──────────────────────────────────────────────
# Component Schema Tests
# ──────────────────────────────────────────────

class TestGraphStoreComponentSchema:
    """Test graph-store component schema validation."""

    def test_minimal_neo4j_config(self):
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "neo4j",
            "actions": [],
        })
        assert config.type.value == "graph-store"
        assert config.driver == GraphStoreDriver.NEO4J
        assert config.url is None
        assert config.host == "localhost"
        assert config.port == 7687
        assert config.protocol == "bolt"
        assert config.username is None
        assert config.password is None
        assert config.database is None
        assert config.timeout == "30s"

    def test_full_neo4j_config(self):
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "neo4j",
            "url": "neo4j://db.example.com:7687",
            "username": "neo4j",
            "password": "secret",
            "database": "mydb",
            "timeout": "60s",
            "actions": [],
        })
        assert config.url == "neo4j://db.example.com:7687"
        assert config.username == "neo4j"
        assert config.password == "secret"
        assert config.database == "mydb"
        assert config.timeout == "60s"

    def test_minimal_arangodb_config(self):
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "arangodb",
            "actions": [],
        })
        assert config.type.value == "graph-store"
        assert config.driver == GraphStoreDriver.ARANGODB
        assert config.host == "localhost"
        assert config.port == 8529
        assert config.protocol == "http"
        assert config.database == "_system"

    def test_full_arangodb_config(self):
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "arangodb",
            "host": "arango.example.com",
            "port": 8530,
            "protocol": "https",
            "username": "root",
            "password": "secret",
            "database": "social",
            "timeout": "60s",
            "actions": [],
        })
        assert config.host == "arango.example.com"
        assert config.port == 8530
        assert config.protocol == "https"
        assert config.username == "root"
        assert config.password == "secret"
        assert config.database == "social"

    def test_invalid_driver(self):
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "graph",
                "type": "graph-store",
                "driver": "unknown-driver",
                "actions": [],
            })

    def test_invalid_arangodb_port(self):
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "graph",
                "type": "graph-store",
                "driver": "arangodb",
                "port": 99999,
                "actions": [],
            })

    def test_neo4j_url_and_host_exclusive(self):
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "graph",
                "type": "graph-store",
                "driver": "neo4j",
                "url": "bolt://remote:7687",
                "host": "remote",
                "actions": [],
            })

    def test_arangodb_url_and_host_exclusive(self):
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "graph",
                "type": "graph-store",
                "driver": "arangodb",
                "url": "http://remote:8529",
                "host": "remote",
                "actions": [],
            })

    def test_neo4j_url_only(self):
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "neo4j",
            "url": "neo4j+s://db.example.com:7687",
            "actions": [],
        })
        assert config.url == "neo4j+s://db.example.com:7687"

    def test_arangodb_url_only(self):
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "arangodb",
            "url": "https://arango.example.com:8529",
            "actions": [],
        })
        assert config.url == "https://arango.example.com:8529"

    def test_neo4j_isinstance(self):
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "neo4j",
            "actions": [],
        })
        assert isinstance(config, Neo4jGraphStoreComponentConfig)

    def test_arangodb_isinstance(self):
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "arangodb",
            "actions": [],
        })
        assert isinstance(config, ArangoDBGraphStoreComponentConfig)


# ──────────────────────────────────────────────
# Neo4j Action Schema Tests
# ──────────────────────────────────────────────

class TestNeo4jActionSchema:
    """Test Neo4j graph store action schema validation."""

    def test_query_action(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "query",
            "query": "MATCH (n:Person) RETURN n",
        })
        assert isinstance(config, Neo4jGraphQueryActionConfig)
        assert config.method == GraphStoreActionMethod.QUERY
        assert config.query == "MATCH (n:Person) RETURN n"
        assert config.params is None
        assert config.database is None

    def test_query_action_with_params(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "query",
            "query": "MATCH (n:Person {name: $name}) RETURN n",
            "params": {"name": "Alice"},
            "database": "mydb",
        })
        assert config.params == {"name": "Alice"}
        assert config.database == "mydb"

    def test_insert_action_with_nodes(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "insert",
            "nodes": {
                "label": "Person",
                "properties": {"name": "Alice", "age": 30},
            },
        })
        assert isinstance(config, Neo4jGraphInsertActionConfig)
        assert config.method == GraphStoreActionMethod.INSERT
        assert config.nodes.label == "Person"
        assert config.relationships is None

    def test_insert_action_with_relationships(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "insert",
            "relationships": {
                "type": "KNOWS",
                "from": "node1",
                "to": "node2",
                "properties": {"since": 2020},
            },
        })
        assert isinstance(config, Neo4jGraphInsertActionConfig)
        assert config.relationships.type == "KNOWS"
        assert config.nodes is None

    def test_insert_action_with_multiple_nodes(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "insert",
            "nodes": [
                {"label": "Person", "properties": {"name": "Alice"}},
                {"label": "Person", "properties": {"name": "Bob"}},
            ],
        })
        assert isinstance(config.nodes, list)
        assert len(config.nodes) == 2

    def test_update_action(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "update",
            "node_id": "4:abc:123",
            "properties": {"age": 31},
            "labels": "Senior",
        })
        assert isinstance(config, Neo4jGraphUpdateActionConfig)
        assert config.node_id == "4:abc:123"
        assert config.properties == {"age": 31}
        assert config.labels == "Senior"

    def test_update_action_multiple_labels(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "update",
            "node_id": "4:abc:123",
            "labels": ["Senior", "Manager"],
        })
        assert config.labels == ["Senior", "Manager"]

    def test_update_relationship(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "update",
            "relationship_id": "5:abc:456",
            "properties": {"weight": 0.9},
        })
        assert config.relationship_id == "5:abc:456"
        assert config.node_id is None

    def test_delete_action_with_detach(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "delete",
            "node_id": "4:abc:123",
            "detach": True,
        })
        assert isinstance(config, Neo4jGraphDeleteActionConfig)
        assert config.detach is True

    def test_delete_action_without_detach(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "delete",
            "node_id": "4:abc:123",
            "detach": False,
        })
        assert config.detach is False

    def test_delete_action_default_detach(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "delete",
            "node_id": "4:abc:123",
        })
        assert config.detach is True

    def test_delete_relationship(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "delete",
            "relationship_id": "5:abc:456",
        })
        assert config.relationship_id == "5:abc:456"
        assert config.node_id is None

    def test_traverse_action_minimal(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "traverse",
            "start_node": "4:abc:123",
        })
        assert isinstance(config, Neo4jGraphTraverseActionConfig)
        assert config.direction == "out"
        assert config.max_depth == 3
        assert config.relationship_types is None
        assert config.node_labels is None

    def test_traverse_action_full(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "traverse",
            "start_node": "4:abc:123",
            "direction": "both",
            "max_depth": 5,
            "relationship_types": ["KNOWS", "WORKS_WITH"],
            "node_labels": ["Person"],
            "database": "mydb",
        })
        assert config.direction == "both"
        assert config.max_depth == 5
        assert config.relationship_types == ["KNOWS", "WORKS_WITH"]
        assert config.node_labels == ["Person"]
        assert config.database == "mydb"

    def test_traverse_invalid_max_depth(self):
        with pytest.raises(ValidationError):
            Neo4jActionAdapter.validate_python({
                "method": "traverse",
                "start_node": "4:abc:123",
                "max_depth": 0,
            })

    def test_traverse_invalid_direction(self):
        with pytest.raises(ValidationError):
            Neo4jActionAdapter.validate_python({
                "method": "traverse",
                "start_node": "4:abc:123",
                "direction": "diagonal",
            })

    def test_action_discriminator(self):
        """Test that method discriminator correctly routes to the right config type."""
        methods_and_types = [
            ({"method": "query", "query": "RETURN 1"}, Neo4jGraphQueryActionConfig),
            ({"method": "insert"}, Neo4jGraphInsertActionConfig),
            ({"method": "update"}, Neo4jGraphUpdateActionConfig),
            ({"method": "delete"}, Neo4jGraphDeleteActionConfig),
            ({"method": "traverse", "start_node": "x"}, Neo4jGraphTraverseActionConfig),
        ]
        for data, expected_type in methods_and_types:
            config = Neo4jActionAdapter.validate_python(data)
            assert isinstance(config, expected_type), f"Expected {expected_type} for method={data['method']}"


# ──────────────────────────────────────────────
# ArangoDB Action Schema Tests
# ──────────────────────────────────────────────

class TestArangoDBActionSchema:
    """Test ArangoDB graph store action schema validation."""

    def test_query_action(self):
        config = ArangoDBActionAdapter.validate_python({
            "method": "query",
            "query": "FOR p IN persons RETURN p",
        })
        assert isinstance(config, ArangoDBGraphQueryActionConfig)
        assert config.query == "FOR p IN persons RETURN p"
        assert config.collection is None

    def test_query_action_with_collection(self):
        config = ArangoDBActionAdapter.validate_python({
            "method": "query",
            "query": "FOR p IN @@col RETURN p",
            "params": {"@col": "persons"},
            "collection": "persons",
        })
        assert config.collection == "persons"
        assert config.params == {"@col": "persons"}

    def test_insert_action_with_graph(self):
        config = ArangoDBActionAdapter.validate_python({
            "method": "insert",
            "collection": "persons",
            "edge_collection": "friendships",
            "graph": "social_graph",
            "nodes": {"label": "persons", "properties": {"name": "Alice"}},
            "relationships": {"type": "friendships", "from": "persons/1", "to": "persons/2"},
        })
        assert isinstance(config, ArangoDBGraphInsertActionConfig)
        assert config.collection == "persons"
        assert config.edge_collection == "friendships"
        assert config.graph == "social_graph"

    def test_update_action(self):
        config = ArangoDBActionAdapter.validate_python({
            "method": "update",
            "collection": "persons",
            "node_id": "persons/12345",
            "properties": {"age": 31},
        })
        assert isinstance(config, ArangoDBGraphUpdateActionConfig)
        assert config.collection == "persons"

    def test_delete_action(self):
        config = ArangoDBActionAdapter.validate_python({
            "method": "delete",
            "collection": "persons",
            "node_id": "persons/12345",
        })
        assert isinstance(config, ArangoDBGraphDeleteActionConfig)

    def test_traverse_action_with_graph(self):
        config = ArangoDBActionAdapter.validate_python({
            "method": "traverse",
            "start_node": "persons/12345",
            "graph": "social_graph",
            "direction": "both",
            "max_depth": 4,
        })
        assert isinstance(config, ArangoDBGraphTraverseActionConfig)
        assert config.graph == "social_graph"
        assert config.edge_collection is None

    def test_traverse_action_with_edge_collection(self):
        config = ArangoDBActionAdapter.validate_python({
            "method": "traverse",
            "start_node": "persons/12345",
            "edge_collection": "friendships",
            "direction": "out",
        })
        assert config.edge_collection == "friendships"
        assert config.graph is None

    def test_action_discriminator(self):
        """Test that method discriminator correctly routes to the right config type."""
        methods_and_types = [
            ({"method": "query", "query": "RETURN 1"}, ArangoDBGraphQueryActionConfig),
            ({"method": "insert"}, ArangoDBGraphInsertActionConfig),
            ({"method": "update"}, ArangoDBGraphUpdateActionConfig),
            ({"method": "delete"}, ArangoDBGraphDeleteActionConfig),
            ({"method": "traverse", "start_node": "x"}, ArangoDBGraphTraverseActionConfig),
        ]
        for data, expected_type in methods_and_types:
            config = ArangoDBActionAdapter.validate_python(data)
            assert isinstance(config, expected_type), f"Expected {expected_type} for method={data['method']}"


# ──────────────────────────────────────────────
# Integration Tests (Component + Actions)
# ──────────────────────────────────────────────

class TestGraphStoreIntegration:
    """Test full component configs with embedded actions."""

    def test_neo4j_component_with_actions(self):
        config = ComponentAdapter.validate_python({
            "id": "knowledge-graph",
            "type": "graph-store",
            "driver": "neo4j",
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password",
            "actions": [
                {
                    "id": "add-person",
                    "method": "insert",
                    "nodes": {"label": "Person", "properties": {"name": "${input.name}"}},
                },
                {
                    "id": "find-person",
                    "method": "query",
                    "query": "MATCH (p:Person {name: $name}) RETURN p",
                    "params": {"name": "${input.name}"},
                },
                {
                    "id": "find-connections",
                    "method": "traverse",
                    "start_node": "${input.node_id}",
                    "direction": "both",
                    "max_depth": 2,
                    "relationship_types": ["KNOWS"],
                },
                {
                    "id": "remove-person",
                    "method": "delete",
                    "node_id": "${input.node_id}",
                    "detach": True,
                },
            ],
        })
        assert isinstance(config, Neo4jGraphStoreComponentConfig)
        assert len(config.actions) == 4
        assert config.actions[0].id == "add-person"
        assert isinstance(config.actions[0], Neo4jGraphInsertActionConfig)
        assert isinstance(config.actions[1], Neo4jGraphQueryActionConfig)
        assert isinstance(config.actions[2], Neo4jGraphTraverseActionConfig)
        assert isinstance(config.actions[3], Neo4jGraphDeleteActionConfig)

    def test_arangodb_component_with_actions(self):
        config = ComponentAdapter.validate_python({
            "id": "social-graph",
            "type": "graph-store",
            "driver": "arangodb",
            "host": "localhost",
            "port": 8529,
            "username": "root",
            "password": "password",
            "database": "social",
            "actions": [
                {
                    "id": "add-person",
                    "method": "insert",
                    "collection": "persons",
                    "nodes": {"label": "persons", "properties": {"name": "${input.name}"}},
                },
                {
                    "id": "find-friends",
                    "method": "query",
                    "query": "FOR p IN persons FILTER p.name == @name RETURN p",
                    "params": {"name": "${input.name}"},
                },
                {
                    "id": "traverse",
                    "method": "traverse",
                    "start_node": "${input.node_id}",
                    "graph": "social_graph",
                    "direction": "both",
                    "max_depth": 2,
                },
            ],
        })
        assert isinstance(config, ArangoDBGraphStoreComponentConfig)
        assert len(config.actions) == 3
        assert isinstance(config.actions[0], ArangoDBGraphInsertActionConfig)
        assert isinstance(config.actions[1], ArangoDBGraphQueryActionConfig)
        assert isinstance(config.actions[2], ArangoDBGraphTraverseActionConfig)

    def test_neo4j_single_action_inflate(self):
        """Test that a single 'action' field is inflated to 'actions' list."""
        config = ComponentAdapter.validate_python({
            "id": "graph",
            "type": "graph-store",
            "driver": "neo4j",
            "action": {
                "method": "query",
                "query": "MATCH (n) RETURN n LIMIT 10",
            },
        })
        assert len(config.actions) == 1
        assert isinstance(config.actions[0], Neo4jGraphQueryActionConfig)


# ──────────────────────────────────────────────
# Identifier Validation Tests
# ──────────────────────────────────────────────

class TestIdentifierValidation:
    """Test that identifiers used in query construction are validated."""

    def test_valid_node_label(self):
        config = Neo4jActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "Person", "properties": {"name": "Alice"}},
        })
        assert config.nodes.label == "Person"

    def test_invalid_node_label_rejected(self):
        with pytest.raises(ValidationError):
            Neo4jActionAdapter.validate_python({
                "method": "insert",
                "nodes": {"label": "Person; DROP", "properties": {}},
            })

    def test_invalid_relationship_type_rejected(self):
        with pytest.raises(ValidationError):
            Neo4jActionAdapter.validate_python({
                "method": "insert",
                "relationships": {"type": "KNOWS}->(b) //", "from": "a", "to": "b"},
            })

    def test_template_variable_allowed_in_label(self):
        """Labels containing ${...} are deferred to runtime rendering."""
        config = Neo4jActionAdapter.validate_python({
            "method": "insert",
            "nodes": {"label": "${input.label}", "properties": {}},
        })
        assert config.nodes.label == "${input.label}"

    def test_invalid_update_label_rejected(self):
        with pytest.raises(ValidationError):
            Neo4jActionAdapter.validate_python({
                "method": "update",
                "node_id": "4:abc:1",
                "labels": "Bad Label!",
            })

    def test_invalid_traverse_relationship_type_rejected(self):
        with pytest.raises(ValidationError):
            Neo4jActionAdapter.validate_python({
                "method": "traverse",
                "start_node": "4:abc:1",
                "relationship_types": ["KNOWS", "bad;type"],
            })

    def test_invalid_arangodb_collection_rejected(self):
        with pytest.raises(ValidationError):
            ArangoDBActionAdapter.validate_python({
                "method": "insert",
                "collection": "bad collection!",
                "nodes": {"label": "persons", "properties": {}},
            })

    def test_invalid_arangodb_edge_collection_rejected(self):
        with pytest.raises(ValidationError):
            ArangoDBActionAdapter.validate_python({
                "method": "traverse",
                "start_node": "persons/1",
                "edge_collection": "bad;edge",
            })
