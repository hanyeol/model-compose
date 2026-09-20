import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mindor.dsl.schema.component import ComponentType, VectorStoreDriverType
from mindor.dsl.schema.component.impl.vector_store.impl.qdrant import QdrantVectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.component.services.vector_store.base import VectorStoreDriverRegistry
from mindor.core.component.services.vector_store.vector_store import VectorStoreComponent
from mindor.core.component.services.vector_store.drivers.qdrant import (
    QdrantVectorStoreService,
    QdrantVectorStoreAction,
    QdrantFilterSpecBuilder,
)


def test_qdrant_driver_registration():
    """Verify QdrantVectorStoreService is registered in VectorStoreDriverRegistry."""
    assert VectorStoreDriverType.QDRANT in VectorStoreDriverRegistry
    assert VectorStoreDriverRegistry[VectorStoreDriverType.QDRANT] is QdrantVectorStoreService


def test_vector_store_component_loads_qdrant():
    """Verify VectorStoreComponent creates QdrantVectorStoreService driver successfully."""
    config = QdrantVectorStoreComponentConfig(
        type=ComponentType.VECTOR_STORE,
        driver=VectorStoreDriverType.QDRANT,
        url="http://localhost:6333",
    )
    global_configs = MagicMock()
    comp = VectorStoreComponent(id="qdrant_comp", config=config, global_configs=global_configs, daemon=False)

    assert isinstance(comp.driver, QdrantVectorStoreService)


def test_qdrant_connection_params_resolution_url():
    """Verify URL-based connection params resolution."""
    config = QdrantVectorStoreComponentConfig(
        type=ComponentType.VECTOR_STORE,
        driver=VectorStoreDriverType.QDRANT,
        url="http://qdrant.cluster:6333",
        api_key="secret-key",
        timeout="10s",
    )
    service = QdrantVectorStoreService(id="test_qdrant", config=config, daemon=False)
    params = service._resolve_connection_params()

    assert params["url"] == "http://qdrant.cluster:6333"
    assert params["api_key"] == "secret-key"
    assert params["timeout"] == 10.0


def test_qdrant_connection_params_resolution_host_port():
    """Verify host/port connection params resolution."""
    config = QdrantVectorStoreComponentConfig(
        type=ComponentType.VECTOR_STORE,
        driver=VectorStoreDriverType.QDRANT,
        host="127.0.0.1",
        port=6333,
        grpc_port=6334,
        prefer_grpc=True,
        https=True,
    )
    service = QdrantVectorStoreService(id="test_qdrant", config=config, daemon=False)
    params = service._resolve_connection_params()

    assert params["host"] == "127.0.0.1"
    assert params["port"] == 6334
    assert params["https"] is True
    assert params["prefer_grpc"] is True


def test_qdrant_filter_builder_empty():
    """Verify empty or None filter returns None."""
    builder = QdrantFilterSpecBuilder()
    assert builder.build(None) is None
    assert builder.build({}) is None


def test_qdrant_filter_builder_dict():
    """Verify dict filter construction."""
    builder = QdrantFilterSpecBuilder()
    filter_spec = builder.build({"category": "electronics", "price": 100})
    assert filter_spec is not None


def test_qdrant_filter_builder_condition():
    """Verify VectorStoreFilterCondition handling."""
    builder = QdrantFilterSpecBuilder()
    cond_eq = VectorStoreFilterCondition(field="status", operator=VectorStoreFilterOperator.EQ, value="active")
    cond_gt = VectorStoreFilterCondition(field="age", operator=VectorStoreFilterOperator.GT, value=21)

    spec = builder.build([cond_eq, cond_gt])
    assert spec is not None


def test_qdrant_action_insert_mocked():
    """Verify QdrantVectorStoreAction insert method with mocked Qdrant client."""
    async def _run():
        mock_client = AsyncMock()
        mock_upsert_res = MagicMock()
        mock_upsert_res.status = "completed"
        mock_client.upsert.return_value = mock_upsert_res

        config = MagicMock()
        action = QdrantVectorStoreAction(config=config, client=mock_client)

        params = {"id_field": "id", "vector_field": "vector"}
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        metadatas = [{"tag": "a"}, {"tag": "b"}]

        result = await action._insert("test_coll", vector_ids=["p1", "p2"], vectors=vectors, metadatas=metadatas, params=params, cancellation_token=None)

        assert result["affected_rows"] == 2
        assert mock_client.upsert.called

    asyncio.run(_run())


def test_qdrant_action_search_mocked():
    """Verify QdrantVectorStoreAction search method with mocked Qdrant client."""
    async def _run():
        mock_client = AsyncMock()
        mock_hit1 = MagicMock()
        mock_hit1.id = "p1"
        mock_hit1.score = 0.95
        mock_hit1.vector = [0.1, 0.2, 0.3]
        mock_hit1.payload = {"name": "doc1"}

        mock_client.search.return_value = [mock_hit1]

        config = MagicMock()
        action = QdrantVectorStoreAction(config=config, client=mock_client)

        params = {"top_k": 5, "filter": None, "output_fields": None}
        queries = [[0.1, 0.2, 0.3]]

        results = await action._search("test_coll", queries=queries, params=params, cancellation_token=None)

        assert len(results) == 1
        assert len(results[0]) == 1
        assert results[0][0]["id"] == "p1"
        assert results[0][0]["score"] == 0.95
        assert results[0][0]["metadata"] == {"name": "doc1"}

    asyncio.run(_run())


def test_qdrant_action_delete_mocked():
    """Verify QdrantVectorStoreAction delete method with mocked Qdrant client."""
    async def _run():
        mock_client = AsyncMock()
        mock_del_res = MagicMock()
        mock_client.delete.return_value = mock_del_res

        config = MagicMock()
        action = QdrantVectorStoreAction(config=config, client=mock_client)

        result = await action._delete("test_coll", vector_ids=["p1", "p2"], params={}, cancellation_token=None)

        assert result["affected_rows"] == 2
        assert mock_client.delete.called

    asyncio.run(_run())
