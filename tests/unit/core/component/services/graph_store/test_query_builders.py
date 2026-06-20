"""Tests for identifier validation in the Neo4j and ArangoDB query builders.

These guard against Cypher/AQL injection through user-supplied labels,
relationship types, and collection names. Validation lives in the driver
layer (the query builder is what assembles the final string), not in the
pydantic schema — the schema accepts arbitrary strings because templates
like ``${input.label}`` are deferred to runtime rendering.
"""

import pytest

from mindor.core.component.services.graph_store.drivers.neo4j import (
    Neo4jQueryBuilder,
)
from mindor.core.component.services.graph_store.drivers.arangodb import (
    ArangoDBQueryBuilder,
)


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

    def test_build_create_node_rejects_bad_label(self):
        with pytest.raises(ValueError, match="Invalid label identifier"):
            Neo4jQueryBuilder.build_create_node("Person; DROP", {"name": "x"})


class TestArangoDBIdentifierValidation:
    def test_valid_collection_passes(self):
        assert ArangoDBQueryBuilder.verify_identifier("persons", "collection") == "persons"

    def test_collection_with_space_rejected(self):
        with pytest.raises(ValueError, match="Invalid collection identifier"):
            ArangoDBQueryBuilder.verify_identifier("bad collection!", "collection")

    def test_edge_collection_with_semicolon_rejected(self):
        with pytest.raises(ValueError, match="Invalid edge_collection identifier"):
            ArangoDBQueryBuilder.verify_identifier("bad;edge", "edge_collection")

    def test_resolve_doc_id_rejects_bad_collection_prefix(self):
        with pytest.raises(ValueError, match="Invalid collection identifier"):
            ArangoDBQueryBuilder.resolve_doc_id("bad collection!/abc", "default")
