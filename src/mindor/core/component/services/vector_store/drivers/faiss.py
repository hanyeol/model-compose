from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any, Union
import ulid, os, json

from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VectorStoreDriver, VectorStoreDriverType, register_vector_store_driver
from ..base import ComponentActionContext
from .common import VectorStoreAction


def _get_faiss_and_np():
    try:
        import faiss
        import numpy as np
        return faiss, np
    except ImportError:
        return None, None


class FaissIndexManager:
    """Manages an in-memory and file-persisted FAISS vector index with metadata storage."""

    def __init__(self, metric: str = "l2", storage_dir: Optional[str] = None):
        self.metric = metric.lower()
        self.storage_dir = storage_dir
        self.index: Any = None
        self.dim: Optional[int] = None
        self.id_to_str: Dict[int, str] = {}
        self.str_to_id: Dict[str, int] = {}
        self.payloads: Dict[str, Dict[str, Any]] = {}
        self.vectors_store: Dict[str, List[float]] = {}
        self._next_int_id: int = 1

    def _ensure_index(self, dim: int):
        if self.index is not None and self.dim == dim:
            return

        self.dim = dim
        faiss, np = _get_faiss_and_np()

        if faiss:
            if self.metric in ("ip", "cosine", "inner_product"):
                base_idx = faiss.IndexFlatIP(dim)
            else:
                base_idx = faiss.IndexFlatL2(dim)
            self.index = faiss.IndexIDMap2(base_idx)
        else:
            self.index = "fallback"

    def insert(
        self,
        vector_ids: Optional[List[Any]],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        if not vectors:
            return 0

        dim = len(vectors[0])
        self._ensure_index(dim)

        count = len(vectors)
        if not vector_ids:
            vector_ids = [str(ulid.new()) for _ in range(count)]
        if not metadatas:
            metadatas = [{} for _ in range(count)]

        int_ids: List[int] = []
        for str_id in vector_ids:
            str_id = str(str_id)
            if str_id in self.str_to_id:
                int_id = self.str_to_id[str_id]
            else:
                int_id = self._next_int_id
                self._next_int_id += 1
                self.str_to_id[str_id] = int_id
                self.id_to_str[int_id] = str_id
            int_ids.append(int_id)

        for str_id, vec, meta in zip(vector_ids, vectors, metadatas):
            str_id = str(str_id)
            self.payloads[str_id] = meta or {}
            self.vectors_store[str_id] = vec

        faiss, np = _get_faiss_and_np()
        if faiss and self.index and self.index != "fallback":
            np_vecs = np.array(vectors, dtype=np.float32)
            np_ids = np.array(int_ids, dtype=np.int64)
            if self.metric == "cosine":
                faiss.normalize_L2(np_vecs)
            self.index.add_with_ids(np_vecs, np_ids)

        return count

    def update(
        self,
        vector_ids: List[Any],
        vectors: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        count = len(vector_ids)
        faiss, np = _get_faiss_and_np()

        for i, vid in enumerate(vector_ids):
            str_id = str(vid)
            meta = metadatas[i] if metadatas and i < len(metadatas) else None
            vec = vectors[i] if vectors and i < len(vectors) else None

            if meta is not None:
                self.payloads[str_id] = meta

            if vec is not None:
                self.vectors_store[str_id] = vec
                if str_id not in self.str_to_id:
                    int_id = self._next_int_id
                    self._next_int_id += 1
                    self.str_to_id[str_id] = int_id
                    self.id_to_str[int_id] = str_id

                int_id = self.str_to_id[str_id]
                if faiss and self.index and self.index != "fallback":
                    np_id = np.array([int_id], dtype=np.int64)
                    self.index.remove_ids(np_id)
                    np_vec = np.array([vec], dtype=np.float32)
                    if self.metric == "cosine":
                        faiss.normalize_L2(np_vec)
                    self.index.add_with_ids(np_vec, np_id)

        return count

    def search(
        self,
        queries: List[List[float]],
        top_k: int = 10,
        filter_spec: Any = None,
        output_fields: Optional[List[str]] = None,
    ) -> List[List[Dict[str, Any]]]:
        if not queries:
            return []

        faiss, np = _get_faiss_and_np()
        dim = len(queries[0])
        results = []

        if faiss and self.index and self.index != "fallback" and self.index.ntotal > 0:
            np_queries = np.array(queries, dtype=np.float32)
            if self.metric == "cosine":
                faiss.normalize_L2(np_queries)

            distances, indices = self.index.search(np_queries, min(top_k * 5, self.index.ntotal))

            for q_idx in range(len(queries)):
                hits = []
                for dist, int_id in zip(distances[q_idx], indices[q_idx]):
                    if int_id == -1 or int_id not in self.id_to_str:
                        continue
                    str_id = self.id_to_str[int_id]
                    payload = self.payloads.get(str_id, {})

                    if not self._eval_filter(payload, filter_spec):
                        continue

                    if output_fields:
                        payload = {k: payload[k] for k in output_fields if k in payload}

                    score = float(dist) if self.metric in ("ip", "cosine") else float(1.0 / (1.0 + dist))

                    hits.append({
                        "id": str_id,
                        "score": score,
                        "distance": float(dist),
                        "vector": self.vectors_store.get(str_id),
                        "metadata": payload,
                        "payload": payload,
                    })

                    if len(hits) >= top_k:
                        break

                results.append(hits)
        else:
            # Pure Python / NumPy fallback
            for query in queries:
                hits = []
                q_vec = query
                for str_id, vec in self.vectors_store.items():
                    payload = self.payloads.get(str_id, {})
                    if not self._eval_filter(payload, filter_spec):
                        continue

                    dist = self._calc_dist(q_vec, vec)
                    score = float(dist) if self.metric in ("ip", "cosine") else float(1.0 / (1.0 + dist))

                    out_payload = payload
                    if output_fields:
                        out_payload = {k: payload[k] for k in output_fields if k in payload}

                    hits.append({
                        "id": str_id,
                        "score": score,
                        "distance": dist,
                        "vector": vec,
                        "metadata": out_payload,
                        "payload": out_payload,
                    })

                hits.sort(key=lambda x: x["score"], reverse=True)
                results.append(hits[:top_k])

        return results

    def delete(self, vector_ids: List[Any], filter_spec: Any = None) -> int:
        faiss, np = _get_faiss_and_np()
        deleted = 0

        target_ids = [str(vid) for vid in vector_ids] if vector_ids else []

        if not target_ids and filter_spec:
            for str_id, payload in list(self.payloads.items()):
                if self._eval_filter(payload, filter_spec):
                    target_ids.append(str_id)

        for str_id in target_ids:
            if str_id in self.str_to_id:
                int_id = self.str_to_id[str_id]
                if faiss and self.index and self.index != "fallback":
                    np_id = np.array([int_id], dtype=np.int64)
                    self.index.remove_ids(np_id)
                del self.str_to_id[str_id]
                del self.id_to_str[int_id]
                self.payloads.pop(str_id, None)
                self.vectors_store.pop(str_id, None)
                deleted += 1

        return deleted

    def _calc_dist(self, vec1: List[float], vec2: List[float]) -> float:
        if self.metric in ("ip", "cosine"):
            return sum(a * b for a, b in zip(vec1, vec2))
        return sum((a - b) ** 2 for a, b in zip(vec1, vec2))

    def _eval_filter(self, payload: Dict[str, Any], filter_spec: Any) -> bool:
        if not filter_spec:
            return True

        if isinstance(filter_spec, dict):
            for k, v in filter_spec.items():
                if payload.get(k) != v:
                    return False
            return True

        if isinstance(filter_spec, VectorStoreFilterCondition):
            field_val = payload.get(filter_spec.field)
            op = filter_spec.operator
            val = filter_spec.value

            if op == VectorStoreFilterOperator.EQ:
                return field_val == val
            if op == VectorStoreFilterOperator.NEQ:
                return field_val != val
            if op == VectorStoreFilterOperator.GT:
                return field_val is not None and field_val > val
            if op == VectorStoreFilterOperator.GTE:
                return field_val is not None and field_val >= val
            if op == VectorStoreFilterOperator.LT:
                return field_val is not None and field_val < val
            if op == VectorStoreFilterOperator.LTE:
                return field_val is not None and field_val <= val
            if op == VectorStoreFilterOperator.IN:
                return field_val in (val if isinstance(val, (list, tuple, set)) else [val])
            if op == VectorStoreFilterOperator.NOT_IN:
                return field_val not in (val if isinstance(val, (list, tuple, set)) else [val])

        if isinstance(filter_spec, (list, tuple)):
            return all(self._eval_filter(payload, item) for item in filter_spec)

        return True


class FaissVectorStoreAction(VectorStoreAction):
    def __init__(self, config: VectorStoreActionConfig, index_manager: FaissIndexManager):
        super().__init__(config, index_manager)
        self.index_manager: FaissIndexManager = index_manager

    async def _insert(
        self,
        collection: Any,
        vector_ids: Optional[List[Any]],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        count = self.index_manager.insert(vector_ids=vector_ids, vectors=vectors, metadatas=metadatas)
        return {"affected_rows": count, "status": "completed"}

    async def _update(
        self,
        collection: Any,
        vector_ids: List[Any],
        vectors: Optional[List[List[float]]],
        metadatas: Optional[List[Dict[str, Any]]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        count = self.index_manager.update(vector_ids=vector_ids, vectors=vectors, metadatas=metadatas)
        return {"affected_rows": count, "status": "completed"}

    async def _search(
        self,
        collection: Any,
        queries: List[List[float]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        top_k = int(params.get("top_k") or 10)
        filter_spec = params.get("filter")
        output_fields = params.get("output_fields")

        return self.index_manager.search(
            queries=queries,
            top_k=top_k,
            filter_spec=filter_spec,
            output_fields=output_fields,
        )

    async def _delete(
        self,
        collection: Any,
        vector_ids: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        filter_spec = params.get("filter")
        count = self.index_manager.delete(vector_ids=vector_ids, filter_spec=filter_spec)
        return {"affected_rows": count, "status": "completed"}


@register_vector_store_driver(VectorStoreDriverType.FAISS)
class FaissVectorStoreService(VectorStoreDriver):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)
        storage_dir = getattr(self.config, "storage_dir", None)
        metric = getattr(self.config, "metric", "l2")
        self.index_manager: FaissIndexManager = FaissIndexManager(metric=metric, storage_dir=storage_dir)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return ["faiss-cpu"]

    async def _start(self) -> None:
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await FaissVectorStoreAction(action, self.index_manager).run(context)
