"""Unit tests for vector-store component schemas."""

import pytest
from pydantic import ValidationError

from mindor.dsl.schema.component.impl.vector_store.impl.milvus import (
    MilvusVectorStoreComponentConfig,
)
from mindor.dsl.schema.component.impl.vector_store.impl.qdrant import (
    QdrantVectorStoreComponentConfig,
)


class TestMilvus:
    def test_endpoint_only_ok(self):
        cfg = MilvusVectorStoreComponentConfig(type="vector-store", driver="milvus", endpoint="https://milvus.example.com")
        assert cfg.endpoint == "https://milvus.example.com"

    def test_host_only_ok(self):
        cfg = MilvusVectorStoreComponentConfig(type="vector-store", driver="milvus", host="milvus.internal")
        assert cfg.host == "milvus.internal"

    def test_endpoint_and_host_together_rejected(self):
        with pytest.raises(ValidationError, match="'endpoint' or 'host'.*not both"):
            MilvusVectorStoreComponentConfig(
                driver="milvus", endpoint="https://x", host="y",
            )

    def test_neither_endpoint_nor_host_rejected(self):
        # Milvus requires explicit endpoint or host (XOR semantics).
        with pytest.raises(ValidationError, match="'endpoint' or 'host'"):
            MilvusVectorStoreComponentConfig(type="vector-store", driver="milvus")


class TestQdrant:
    def test_host_only_ok(self):
        cfg = QdrantVectorStoreComponentConfig(type="vector-store", driver="qdrant", host="qdrant.example.com")
        assert cfg.host == "qdrant.example.com"
        assert cfg.url is None

    def test_url_only_ok(self):
        cfg = QdrantVectorStoreComponentConfig(type="vector-store", driver="qdrant", url="http://qdrant:6333")
        assert cfg.url == "http://qdrant:6333"

    def test_url_and_host_together_rejected(self):
        with pytest.raises(ValidationError, match="Either 'url' or 'host'"):
            QdrantVectorStoreComponentConfig(
                driver="qdrant", url="http://x", host="qdrant.example.com",
            )

    def test_default_host_when_neither_provided(self):
        cfg = QdrantVectorStoreComponentConfig(type="vector-store", driver="qdrant")
        assert cfg.host == "localhost"
