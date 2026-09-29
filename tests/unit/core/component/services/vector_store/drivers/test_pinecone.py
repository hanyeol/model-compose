import asyncio
import pytest
from unittest.mock import MagicMock, patch
from mindor.dsl.schema.component import ComponentType, VectorStoreDriverType
from mindor.dsl.schema.component.impl.vector_store.impl.pinecone import PineconeVectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.component.services.vector_store.base import VectorStoreDriverRegistry
from mindor.core.component.services.vector_store.vector_store import VectorStoreComponent
from mindor.core.component.services.vector_store.drivers.pinecone import (
    PineconeVectorStoreService,
    PineconeVectorStoreAction,
    PineconeFilterBuilder,
)


def test_pinecone_driver_registration():
    """Verify PineconeVectorStoreService is registered in VectorStoreDriverRegistry."""
    assert VectorStoreDriverType.PINECONE in VectorStoreDriverRegistry
    assert VectorStoreDriverRegistry[VectorStoreDriverType.PINECONE] is PineconeVectorStoreService


def test_vector_store_component_loads_pinecone():
    """Verify VectorStoreComponent creates PineconeVectorStoreService driver successfully."""
    config = PineconeVectorStoreComponentConfig(
        type=ComponentType.VECTOR_STORE,
        driver=VectorStoreDriverType.PINECONE,
        index_name="test-index",
        api_key="test-key",
    )
    global_configs = MagicMock()
    comp = VectorStoreComponent(id="pinecone_comp", config=config, global_configs=global_configs, daemon=False)

    assert isinstance(comp.driver, PineconeVectorStoreService)


def test_pinecone_filter_builder():
    """Verify PineconeFilterBuilder translates VectorStoreFilterCondition to Pinecone filter dict."""
    builder = PineconeFilterBuilder()

    # EQ
    cond1 = VectorStoreFilterCondition(field="status", operator=VectorStoreFilterOperator.EQ, value="active").model_dump()
    res1 = builder.build(cond1)
    assert res1 == {"status": {"$eq": "active"}}

    # NEQ
    cond2 = VectorStoreFilterCondition(field="status", operator=VectorStoreFilterOperator.NEQ, value="inactive").model_dump()
    res2 = builder.build(cond2)
    assert res2 == {"status": {"$ne": "inactive"}}

    # GT / GTE / LT / LTE
    cond3 = VectorStoreFilterCondition(field="score", operator=VectorStoreFilterOperator.GT, value=10).model_dump()
    assert builder.build(cond3) == {"score": {"$gt": 10}}

    cond4 = VectorStoreFilterCondition(field="score", operator=VectorStoreFilterOperator.GTE, value=10).model_dump()
    assert builder.build(cond4) == {"score": {"$gte": 10}}

    cond5 = VectorStoreFilterCondition(field="score", operator=VectorStoreFilterOperator.LT, value=5).model_dump()
    assert builder.build(cond5) == {"score": {"$lt": 5}}

    cond6 = VectorStoreFilterCondition(field="score", operator=VectorStoreFilterOperator.LTE, value=5).model_dump()
    assert builder.build(cond6) == {"score": {"$lte": 5}}

    # IN / NOT_IN
    cond7 = VectorStoreFilterCondition(field="tag", operator=VectorStoreFilterOperator.IN, value=["a", "b"]).model_dump()
    assert builder.build(cond7) == {"tag": {"$in": ["a", "b"]}}

    cond8 = VectorStoreFilterCondition(field="tag", operator=VectorStoreFilterOperator.NOT_IN, value=["c"]).model_dump()
    assert builder.build(cond8) == {"tag": {"$nin": ["c"]}}

    # Multiple conditions combined with $and
    multi = builder.build([cond1, cond3])
    assert multi == {"$and": [{"status": {"$eq": "active"}}, {"score": {"$gt": 10}}]}


def test_pinecone_action_execution():
    """Verify PineconeVectorStoreAction insert, update, search, and delete with mocked Pinecone client."""
    async def _run():
        mock_index = MagicMock()
        mock_client = MagicMock()
        mock_client.Index.return_value = mock_index

        # Setup query mock return
        mock_index.query.return_value = {
            "matches": [
                {
                    "id": "vec1",
                    "score": 0.95,
                    "values": [0.1, 0.2, 0.3],
                    "metadata": {"category": "A", "hidden": "val"}
                }
            ]
        }

        component_config = PineconeVectorStoreComponentConfig(
            type=ComponentType.VECTOR_STORE,
            driver=VectorStoreDriverType.PINECONE,
            index_name="my-index",
            namespace="prod",
        )
        action_config = MagicMock()

        action = PineconeVectorStoreAction(config=action_config, client=mock_client, component_config=component_config)

        # Insert
        res_ins = await action._insert("my-index", vector_ids=["vec1"], vectors=[[0.1, 0.2, 0.3]], metadatas=[{"category": "A"}], params={}, cancellation_token=None)
        assert res_ins["affected_rows"] == 1
        assert res_ins["ids"] == ["vec1"]
        mock_index.upsert.assert_called_once_with(
            vectors=[{"id": "vec1", "values": [0.1, 0.2, 0.3], "metadata": {"category": "A"}}],
            namespace="prod"
        )

        # Search
        mock_index.reset_mock()
        res_search = await action._search("my-index", queries=[[0.1, 0.2, 0.3]], params={"top_k": 5, "output_fields": ["category"]}, cancellation_token=None)
        assert len(res_search) == 1
        assert len(res_search[0]) == 1
        assert res_search[0][0]["id"] == "vec1"
        assert res_search[0][0]["score"] == 0.95
        assert res_search[0][0]["metadata"] == {"category": "A"}

        # Update
        mock_index.reset_mock()
        res_upd = await action._update("my-index", vector_ids=["vec1"], vectors=[[0.2, 0.3, 0.4]], metadatas=[{"category": "A2"}], params={}, cancellation_token=None)
        assert res_upd["affected_rows"] == 1
        mock_index.upsert.assert_called_once_with(
            vectors=[{"id": "vec1", "values": [0.2, 0.3, 0.4], "metadata": {"category": "A2"}}],
            namespace="prod"
        )

        # Delete by IDs
        mock_index.reset_mock()
        res_del = await action._delete("my-index", vector_ids=["vec1"], params={}, cancellation_token=None)
        assert res_del["affected_rows"] == 1
        mock_index.delete.assert_called_once_with(ids=["vec1"], namespace="prod")

    asyncio.run(_run())
