"""Unit tests for the Neo4j and ArangoDB query builders.

Covers both identifier validation (injection prevention) and the actual Cypher /
AQL string construction. Validation lives in the driver layer, not in the
pydantic schema — the schema accepts arbitrary strings because templates like
``${input.label}`` are deferred to runtime rendering.
"""

import pytest

from mindor.core.component.services.graph_store.drivers.neo4j import (
    Neo4jQueryBuilder,
)
from mindor.core.component.services.graph_store.drivers.arangodb import (
    ArangoDBQueryBuilder,
)


# ──────────────────────────────────────────────
# Identifier validation
# ──────────────────────────────────────────────


class TestNeo4jIdentifierValidation:
    def test_valid_label_passes(self):
        assert Neo4jQueryBuilder.verify_identifier("Person", "label") == "Person"

    def test_label_with_injection_rejected(self):
        with pytest.raises(ValueError, match="Invalid label identifier"):
            Neo4jQueryBuilder.verify_identifier("Person; DROP", "label")

    def test_relationship_type_with_injection_rejected(self):
        with pytest.raises(ValueError, match="Invalid type identifier"):
            Neo4jQueryBuilder.verify_identifier("KNOWS}->(b) //", "type")

    def test_label_with_space_rejected(self):
        with pytest.raises(ValueError, match="Invalid label identifier"):
            Neo4jQueryBuilder.verify_identifier("Bad Label!", "label")

    def test_relationship_type_with_semicolon_rejected(self):
        with pytest.raises(ValueError, match="Invalid type identifier"):
            Neo4jQueryBuilder.verify_identifier("bad;type", "type")

    def test_label_starting_with_digit_rejected(self):
        with pytest.raises(ValueError):
            Neo4jQueryBuilder.verify_identifier("123Node", "label")

    def test_underscore_prefix_label_accepted(self):
        assert Neo4jQueryBuilder.verify_identifier("_private", "label") == "_private"


class TestArangoDBIdentifierValidation:
    def test_valid_collection_passes(self):
        assert ArangoDBQueryBuilder.verify_identifier("persons", "collection") == "persons"

    def test_collection_with_space_rejected(self):
        with pytest.raises(ValueError, match="Invalid collection identifier"):
            ArangoDBQueryBuilder.verify_identifier("bad collection!", "collection")

    def test_edge_collection_with_semicolon_rejected(self):
        with pytest.raises(ValueError, match="Invalid edge_collection identifier"):
            ArangoDBQueryBuilder.verify_identifier("bad;edge", "edge_collection")

    def test_resolve_doc_id_with_slash_splits_into_collection_and_key(self):
        coll, key = ArangoDBQueryBuilder.resolve_doc_id("persons/abc", "default")
        assert coll == "persons"
        assert key == "abc"

    def test_resolve_doc_id_without_slash_uses_default_collection(self):
        coll, key = ArangoDBQueryBuilder.resolve_doc_id("abc", "default")
        assert coll == "default"
        assert key == "abc"

    def test_resolve_doc_id_rejects_bad_collection_prefix(self):
        with pytest.raises(ValueError, match="Invalid collection identifier"):
            ArangoDBQueryBuilder.resolve_doc_id("bad collection!/abc", "default")


# ──────────────────────────────────────────────
# Neo4j Cypher builders
# ──────────────────────────────────────────────


class TestNeo4jBuildCreateNode:
    def test_returns_cypher_and_params(self):
        cypher, params = Neo4jQueryBuilder.build_create_node("Person", {"name": "Alice", "age": 30})
        assert "CREATE (n:Person" in cypher
        assert "name: $name" in cypher
        assert "age: $age" in cypher
        assert "RETURN elementId(n) AS id" in cypher
        assert params == {"name": "Alice", "age": 30}

    def test_empty_properties(self):
        cypher, params = Neo4jQueryBuilder.build_create_node("Tag", {})
        assert "CREATE (n:Tag" in cypher
        assert params == {}

    def test_rejects_bad_label(self):
        with pytest.raises(ValueError, match="Invalid label identifier"):
            Neo4jQueryBuilder.build_create_node("Person; DROP", {"name": "x"})


class TestNeo4jBuildCreateRelationship:
    def test_with_properties(self):
        cypher, params = Neo4jQueryBuilder.build_create_relationship(
            "KNOWS", "4:a:1", "4:b:2", {"since": 2020}
        )
        assert "[r:KNOWS {since: $prop_since}]" in cypher
        assert "elementId(a) = $from_id" in cypher
        assert "elementId(b) = $to_id" in cypher
        assert params == {"from_id": "4:a:1", "to_id": "4:b:2", "prop_since": 2020}

    def test_without_properties_omits_property_braces(self):
        cypher, params = Neo4jQueryBuilder.build_create_relationship(
            "KNOWS", "4:a:1", "4:b:2", {}
        )
        assert "[r:KNOWS]" in cypher
        assert "{" not in cypher.split("[r:KNOWS]")[1].split("RETURN")[0]
        assert params == {"from_id": "4:a:1", "to_id": "4:b:2"}

    def test_rejects_bad_relationship_type(self):
        with pytest.raises(ValueError, match="Invalid relationship type identifier"):
            Neo4jQueryBuilder.build_create_relationship("BAD;TYPE", "a", "b", {})


class TestNeo4jBuildUpdateNode:
    def test_properties_only(self):
        cypher, params = Neo4jQueryBuilder.build_update_node("4:x:1", {"name": "Bob"}, None)
        assert "n.name = $prop_name" in cypher
        assert "MATCH (n) WHERE elementId(n) = $id" in cypher
        assert params == {"id": "4:x:1", "prop_name": "Bob"}

    def test_labels_only_string(self):
        cypher, params = Neo4jQueryBuilder.build_update_node("4:x:1", None, "Active")
        assert "SET n:Active" in cypher
        assert params == {"id": "4:x:1"}

    def test_labels_only_list(self):
        cypher, params = Neo4jQueryBuilder.build_update_node("4:x:1", None, ["A", "B"])
        assert "SET n:A" in cypher
        assert "SET n:B" in cypher

    def test_properties_and_labels(self):
        cypher, params = Neo4jQueryBuilder.build_update_node("4:x:1", {"k": "v"}, "Tag")
        assert "n.k = $prop_k" in cypher
        assert "SET n:Tag" in cypher

    def test_no_changes_returns_none(self):
        assert Neo4jQueryBuilder.build_update_node("4:x:1", None, None) is None
        assert Neo4jQueryBuilder.build_update_node("4:x:1", {}, []) is None

    def test_rejects_bad_label(self):
        with pytest.raises(ValueError, match="Invalid label identifier"):
            Neo4jQueryBuilder.build_update_node("4:x:1", None, "Bad Label!")


class TestNeo4jBuildUpdateRelationship:
    def test_with_properties(self):
        cypher, params = Neo4jQueryBuilder.build_update_relationship(
            "5:r:1", {"weight": 0.5, "kind": "strong"}
        )
        assert "r.weight = $prop_weight" in cypher
        assert "r.kind = $prop_kind" in cypher
        assert params == {"id": "5:r:1", "prop_weight": 0.5, "prop_kind": "strong"}


class TestNeo4jBuildDelete:
    def test_node_with_detach(self):
        cypher, params = Neo4jQueryBuilder.build_delete_node("4:x:1", detach=True)
        assert "DETACH DELETE n" in cypher
        assert params == {"id": "4:x:1"}

    def test_node_without_detach(self):
        cypher, params = Neo4jQueryBuilder.build_delete_node("4:x:1", detach=False)
        assert "DETACH DELETE n" not in cypher
        assert "DELETE n" in cypher

    def test_relationship(self):
        cypher, params = Neo4jQueryBuilder.build_delete_relationship("5:r:1")
        assert "DELETE r" in cypher
        assert params == {"id": "5:r:1"}


class TestNeo4jBuildTraverse:
    def test_outbound_direction(self):
        cypher, params = Neo4jQueryBuilder.build_traverse(
            "4:x:1", direction="out", max_depth=3, relationship_types=None, node_labels=None,
        )
        assert "(start)-[r*1..3]->(end)" in cypher
        assert "elementId(start) = $start_id" in cypher
        assert params == {"start_id": "4:x:1"}

    def test_inbound_direction(self):
        cypher, _ = Neo4jQueryBuilder.build_traverse(
            "4:x:1", direction="in", max_depth=2, relationship_types=None, node_labels=None,
        )
        assert "(start)<-[r*1..2]-(end)" in cypher

    def test_both_directions_default(self):
        cypher, _ = Neo4jQueryBuilder.build_traverse(
            "4:x:1", direction="both", max_depth=1, relationship_types=None, node_labels=None,
        )
        assert "(start)-[r*1..1]-(end)" in cypher

    def test_relationship_type_filter(self):
        cypher, _ = Neo4jQueryBuilder.build_traverse(
            "4:x:1", direction="out", max_depth=3,
            relationship_types=["KNOWS", "WORKS_WITH"], node_labels=None,
        )
        assert "[r:KNOWS|WORKS_WITH*1..3]" in cypher

    def test_node_label_filter(self):
        cypher, _ = Neo4jQueryBuilder.build_traverse(
            "4:x:1", direction="out", max_depth=2,
            relationship_types=None, node_labels=["Person"],
        )
        assert "ANY(l IN labels(end) WHERE l = 'Person')" in cypher

    def test_rejects_bad_relationship_type(self):
        with pytest.raises(ValueError, match="Invalid relationship type identifier"):
            Neo4jQueryBuilder.build_traverse(
                "4:x:1", direction="out", max_depth=3,
                relationship_types=["bad;rel"], node_labels=None,
            )

    def test_rejects_bad_node_label(self):
        with pytest.raises(ValueError, match="Invalid node label identifier"):
            Neo4jQueryBuilder.build_traverse(
                "4:x:1", direction="out", max_depth=3,
                relationship_types=None, node_labels=["bad label"],
            )


# ──────────────────────────────────────────────
# ArangoDB AQL builders
# ──────────────────────────────────────────────


class TestArangoDBBuildInsertNode:
    def test_uses_label_as_collection(self):
        coll, doc = ArangoDBQueryBuilder.build_insert_node_doc(
            {"label": "persons", "properties": {"name": "Alice"}}, default_collection=None,
        )
        assert coll == "persons"
        assert doc == {"name": "Alice"}

    def test_falls_back_to_default_collection(self):
        coll, _ = ArangoDBQueryBuilder.build_insert_node_doc(
            {"properties": {"name": "Alice"}}, default_collection="people",
        )
        assert coll == "people"

    def test_falls_back_to_nodes_when_no_default(self):
        coll, _ = ArangoDBQueryBuilder.build_insert_node_doc(
            {"properties": {"name": "Alice"}}, default_collection=None,
        )
        assert coll == "nodes"

    def test_id_promoted_to_key(self):
        _, doc = ArangoDBQueryBuilder.build_insert_node_doc(
            {"label": "persons", "id": 42, "properties": {"name": "Alice"}},
            default_collection=None,
        )
        assert doc["_key"] == "42"
        assert doc["name"] == "Alice"

    def test_rejects_bad_collection(self):
        with pytest.raises(ValueError, match="Invalid collection identifier"):
            ArangoDBQueryBuilder.build_insert_node_doc(
                {"label": "bad collection!", "properties": {}}, default_collection=None,
            )
