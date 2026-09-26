import asyncio
import pytest
from unittest.mock import MagicMock
from mindor.dsl.schema.component import ComponentType, VectorStoreDriverType
from mindor.dsl.schema.component.impl.vector_store.impl.faiss import FaissVectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.component.services.vector_store.base import VectorStoreDriverRegistry
from mindor.core.component.services.vector_store.vector_store import VectorStoreComponent
from mindor.core.component.services.vector_store.drivers.faiss import (
    FaissVectorStoreService,
    FaissVectorStoreAction,
    FaissIndexManager,
)

pytest.importorskip("faiss", reason="faiss-cpu is not installed")


def test_faiss_driver_registration():
    """Verify FaissVectorStoreService is registered in VectorStoreDriverRegistry."""
    assert VectorStoreDriverType.FAISS in VectorStoreDriverRegistry
    assert VectorStoreDriverRegistry[VectorStoreDriverType.FAISS] is FaissVectorStoreService


def test_vector_store_component_loads_faiss():
    """Verify VectorStoreComponent creates FaissVectorStoreService driver successfully."""
    config = FaissVectorStoreComponentConfig(
        type=ComponentType.VECTOR_STORE,
        driver=VectorStoreDriverType.FAISS,
        dimension=3,
    )
    global_configs = MagicMock()
    comp = VectorStoreComponent(id="faiss_comp", config=config, global_configs=global_configs, daemon=False)

    assert isinstance(comp.driver, FaissVectorStoreService)


def test_faiss_index_manager_insert_and_search():
    """Verify insertion and vector similarity search in FaissIndexManager."""
    mgr = FaissIndexManager(dimension=3, metric="l2")
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    metadatas = [{"category": "A"}, {"category": "B"}]
    ids = ["doc1", "doc2"]

    count = mgr.insert(vector_ids=ids, vectors=vectors, metadatas=metadatas)
    assert count == 2

    # Query closest to doc1
    results = mgr.search(queries=[[0.9, 0.1, 0.0]], top_k=2)
    assert len(results) == 1
    assert len(results[0]) == 2
    assert results[0][0]["id"] == "doc1"
    assert results[0][0]["metadata"] == {"category": "A"}


def test_faiss_index_manager_filter():
    """Verify metadata filter in FaissIndexManager search."""
    mgr = FaissIndexManager(dimension=2, metric="l2")
    mgr.insert(
        vector_ids=["doc1", "doc2"],
        vectors=[[1.0, 0.0], [0.0, 1.0]],
        metadatas=[{"status": "active"}, {"status": "inactive"}],
    )

    cond = VectorStoreFilterCondition(field="status", operator=VectorStoreFilterOperator.EQ, value="active")
    results = mgr.search(queries=[[1.0, 0.0]], top_k=5, filter=cond)

    assert len(results) == 1
    assert len(results[0]) == 1
    assert results[0][0]["id"] == "doc1"


def test_faiss_index_manager_update():
    """Verify vector and metadata update in FaissIndexManager."""
    mgr = FaissIndexManager(dimension=2, metric="l2")
    mgr.insert(vector_ids=["doc1"], vectors=[[1.0, 0.0]], metadatas=[{"v": 1}])

    count = mgr.update(vector_ids=["doc1"], vectors=[[0.0, 1.0]], metadatas=[{"v": 2}])
    assert count == 1

    results = mgr.search(queries=[[0.0, 1.0]], top_k=1)
    assert results[0][0]["id"] == "doc1"
    assert results[0][0]["metadata"] == {"v": 2}


def test_faiss_index_manager_delete():
    """Verify point deletion in FaissIndexManager."""
    mgr = FaissIndexManager(dimension=2, metric="l2")
    mgr.insert(vector_ids=["doc1", "doc2"], vectors=[[1.0, 0.0], [0.0, 1.0]], metadatas=[{}, {}])

    deleted = mgr.delete(vector_ids=["doc1"])
    assert deleted == 1

    results = mgr.search(queries=[[1.0, 0.0]], top_k=5)
    assert len(results[0]) == 1
    assert results[0][0]["id"] == "doc2"


def test_faiss_index_manager_persistence(tmp_path):
    """Verify index and metadata are persisted to storage_dir and reloaded."""
    storage_dir = str(tmp_path / "faiss_store")

    mgr = FaissIndexManager(dimension=3, metric="cosine", storage_dir=storage_dir)
    mgr.insert(
        vector_ids=["doc1", "doc2"],
        vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        metadatas=[{"category": "A"}, {"category": "B"}],
    )

    # Reopen the store: state should be restored from disk
    reloaded = FaissIndexManager(dimension=3, metric="cosine", storage_dir=storage_dir)

    assert reloaded.index.ntotal == 2
    assert reloaded.state.metadatas == {"doc1": {"category": "A"}, "doc2": {"category": "B"}}
    assert reloaded.state.str_to_id.keys() == {"doc1", "doc2"}

    results = reloaded.search(queries=[[1.0, 0.0, 0.0]], top_k=1)
    assert results[0][0]["id"] == "doc1"
    assert results[0][0]["metadata"] == {"category": "A"}


def test_faiss_index_manager_persistence_dimension_mismatch(tmp_path):
    """Reopening with a different dimension should raise a clear error."""
    storage_dir = str(tmp_path / "faiss_store")

    mgr = FaissIndexManager(dimension=3, metric="l2", storage_dir=storage_dir)
    mgr.insert(vector_ids=["doc1"], vectors=[[1.0, 0.0, 0.0]], metadatas=[{}])

    with pytest.raises(ValueError, match="dimension"):
        FaissIndexManager(dimension=4, metric="l2", storage_dir=storage_dir)


def test_faiss_action_execution():
    """Verify FaissVectorStoreAction execution."""
    async def _run():
        mgr = FaissIndexManager(dimension=2, metric="l2")
        config = MagicMock()
        action = FaissVectorStoreAction(config=config, index_manager=mgr, lock=asyncio.Lock())

        res_ins = await action._insert("coll", vector_ids=["p1"], vectors=[[0.5, 0.5]], metadatas=[{"tag": "x"}], params={}, cancellation_token=None)
        assert res_ins["affected_rows"] == 1

        res_search = await action._search("coll", queries=[[0.5, 0.5]], params={"top_k": 1}, cancellation_token=None)
        assert res_search[0][0]["id"] == "p1"

        res_del = await action._delete("coll", vector_ids=["p1"], params={}, cancellation_token=None)
        assert res_del["affected_rows"] == 1

    asyncio.run(_run())
