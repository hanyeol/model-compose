from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VectorStoreDriver, VectorStoreDriverType, register_vector_store_driver
from ..base import ComponentActionContext
from .common import VectorStoreAction
import ulid, os, json, asyncio

if TYPE_CHECKING:
    import faiss

@dataclass
class FaissIndexState:
    dimension: int
    metric: str
    id_to_str: Dict[int, str] = field(default_factory=dict)
    str_to_id: Dict[str, int] = field(default_factory=dict)
    metadatas: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    vectors: Dict[str, List[float]] = field(default_factory=dict)
    next_int_id: int = 1

class FaissIndexManager:
    """Manages an in-memory FAISS vector index with ID mapping and metadata."""

    def __init__(self, dimension: int, metric: str = "l2", storage_dir: Optional[str] = None):
        self.index, self.state = self._load_index(storage_dir, dimension, metric)
        self.storage_dir = storage_dir

    def insert(
        self,
        vector_ids: Optional[List[Any]],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        import numpy as np
        import faiss

        if len(vectors) == 0:
            return 0

        if len(vectors[0]) != self.state.dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.state.dimension}, got {len(vectors[0])}"
            )

        count = len(vectors)

        if not vector_ids:
            vector_ids = [ str(ulid.new()) for _ in range(count) ]

        if not metadatas:
            metadatas = [ {} for _ in range(count) ]

        int_ids: List[int] = []

        for str_id in vector_ids:
            str_id = str(str_id)

            if str_id in self.state.str_to_id:
                int_id = self.state.str_to_id[str_id]
            else:
                int_id = self.state.next_int_id
                self.state.next_int_id += 1
                self.state.str_to_id[str_id] = int_id
                self.state.id_to_str[int_id] = str_id

            int_ids.append(int_id)

        for str_id, vector, metadata in zip(vector_ids, vectors, metadatas):
            str_id = str(str_id)
            self.state.metadatas[str_id] = metadata or {}
            self.state.vectors[str_id] = vector

        vectors_array = np.array(vectors, dtype=np.float32)
        ids_array = np.array(int_ids, dtype=np.int64)

        if self.state.metric == "cosine":
            faiss.normalize_L2(vectors_array)

        self.index.add_with_ids(vectors_array, ids_array)

        if self.storage_dir:
            self._save_index(self.storage_dir, self.state)

        return count

    def update(
        self,
        vector_ids: List[Any],
        vectors: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        import numpy as np
        import faiss

        count = len(vector_ids)

        for index, vector_id in enumerate(vector_ids):
            str_id = str(vector_id)
            metadata = metadatas[index] if metadatas and index < len(metadatas) else None
            vector = vectors[index] if vectors and index < len(vectors) else None

            if metadata is not None:
                self.state.metadatas[str_id] = metadata

            if vector is not None:
                self.state.vectors[str_id] = vector

                if str_id not in self.state.str_to_id:
                    int_id = self.state.next_int_id
                    self.state.next_int_id += 1
                    self.state.str_to_id[str_id] = int_id
                    self.state.id_to_str[int_id] = str_id

                int_id = self.state.str_to_id[str_id]

                id_array = np.array([ int_id ], dtype=np.int64)
                self.index.remove_ids(id_array)
                vector_array = np.array([ vector ], dtype=np.float32)

                if self.state.metric == "cosine":
                    faiss.normalize_L2(vector_array)

                self.index.add_with_ids(vector_array, id_array)

        if self.storage_dir:
            self._save_index(self.storage_dir, self.state)

        return count

    def search(
        self,
        queries: List[List[float]],
        top_k: int = 10,
        filter: Any = None,
        output_fields: Optional[List[str]] = None,
    ) -> List[List[Dict[str, Any]]]:
        import numpy as np
        import faiss

        if self.index.ntotal == 0 or len(queries) == 0:
            return [ [] for _ in queries ]

        if len(queries[0]) != self.state.dimension:
            raise ValueError(
                f"Query vector dimension mismatch: expected {self.state.dimension}, got {len(queries[0])}"
            )

        queries_array = np.array(queries, dtype=np.float32)

        if self.state.metric == "cosine":
            faiss.normalize_L2(queries_array)

        distances, indices = self.index.search(queries_array, min(top_k * 5, self.index.ntotal))
        results = []

        for index in range(len(queries)):
            hits = []

            for dist, int_id in zip(distances[index], indices[index]):
                if int_id == -1 or int_id not in self.state.id_to_str:
                    continue

                str_id = self.state.id_to_str[int_id]
                metadata = self.state.metadatas.get(str_id, {})

                if not self._evaluate_filter(metadata, filter):
                    continue

                if output_fields:
                    metadata = { field: metadata[field] for field in output_fields if field in metadata }

                score = float(dist) if self.state.metric in ("ip", "cosine") else float(1.0 / (1.0 + dist))

                hits.append({
                    "id": str_id,
                    "score": score,
                    "distance": float(dist),
                    "vector": self.state.vectors.get(str_id),
                    "metadata": metadata,
                })

                if len(hits) >= top_k:
                    break

            results.append(hits)

        return results

    def delete(self, vector_ids: List[Any], filter: Any = None) -> int:
        import numpy as np

        target_ids = [ str(vector_id) for vector_id in vector_ids ] if vector_ids else []

        if not target_ids and filter:
            for str_id, metadata in list(self.state.metadatas.items()):
                if self._evaluate_filter(metadata, filter):
                    target_ids.append(str_id)

        deleted = 0

        for str_id in target_ids:
            if str_id in self.state.str_to_id:
                int_id = self.state.str_to_id[str_id]
                id_array = np.array([int_id], dtype=np.int64)
                self.index.remove_ids(id_array)
                del self.state.str_to_id[str_id]
                del self.state.id_to_str[int_id]
                self.state.metadatas.pop(str_id, None)
                self.state.vectors.pop(str_id, None)
                deleted += 1

        if self.storage_dir:
            self._save_index(self.storage_dir, self.state)

        return deleted

    def _load_index(self, storage_dir: Optional[str], dimension: int, metric: str) -> Tuple[faiss.IndexIDMap2, FaissIndexState]:
        import faiss

        if storage_dir and os.path.exists(self._index_path(storage_dir)):
            with open(self._metadata_path(storage_dir), "r") as f:
                state_dict = json.load(f)

            if state_dict["dimension"] != dimension:
                raise ValueError(
                    f"Persisted index dimension ({state_dict['dimension']}) does not match config ({dimension})"
                )

            if state_dict["metric"] != metric:
                raise ValueError(
                    f"Persisted index metric ({state_dict['metric']}) does not match config ({metric})"
                )

            id_to_str = { int(int_id): str_id for int_id, str_id in state_dict["id_to_str"].items() }
            state = FaissIndexState(
                dimension=state_dict["dimension"],
                metric=state_dict["metric"],
                id_to_str=id_to_str,
                str_to_id={ str_id: int_id for int_id, str_id in id_to_str.items() },
                metadatas=state_dict["metadatas"],
                vectors=state_dict["vectors"],
                next_int_id=state_dict["next_int_id"],
            )
            index = faiss.read_index(self._index_path(storage_dir))
        else:
            if storage_dir:
                os.makedirs(storage_dir, exist_ok=True)

            state = FaissIndexState(dimension=dimension, metric=metric)
            index = self._create_index(dimension, metric)

        return index, state

    def _create_index(self, dimension: int, metric: str) -> faiss.IndexIDMap2:
        import faiss

        if metric in ("ip", "cosine"):
            base_index = faiss.IndexFlatIP(dimension)
        else:
            base_index = faiss.IndexFlatL2(dimension)

        return faiss.IndexIDMap2(base_index)

    def _save_index(self, storage_dir: str, state: FaissIndexState) -> None:
        import faiss

        faiss.write_index(self.index, self._index_path(storage_dir))

        with open(self._metadata_path(storage_dir), "w") as f:
            json.dump(asdict(state), f)

    @staticmethod
    def _index_path(storage_dir: str) -> str:
        return os.path.join(storage_dir, "index.faiss")

    @staticmethod
    def _metadata_path(storage_dir: str) -> str:
        return os.path.join(storage_dir, "metadata.json")

    def _evaluate_filter(self, metadata: Dict[str, Any], filter: Any) -> bool:
        if isinstance(filter, dict):
            for field, value in filter.items():
                if metadata.get(field) != value:
                    return False

            return True

        if isinstance(filter, VectorStoreFilterCondition):
            metadata_value = metadata.get(filter.field)

            if filter.operator == VectorStoreFilterOperator.EQ:
                return metadata_value == filter.value

            if filter.operator == VectorStoreFilterOperator.NEQ:
                return metadata_value != filter.value

            if filter.operator == VectorStoreFilterOperator.GT:
                return metadata_value is not None and metadata_value > filter.value

            if filter.operator == VectorStoreFilterOperator.GTE:
                return metadata_value is not None and metadata_value >= filter.value

            if filter.operator == VectorStoreFilterOperator.LT:
                return metadata_value is not None and metadata_value < filter.value

            if filter.operator == VectorStoreFilterOperator.LTE:
                return metadata_value is not None and metadata_value <= filter.value

            if filter.operator == VectorStoreFilterOperator.IN:
                return metadata_value in (filter.value if isinstance(filter.value, (list, tuple)) else [ filter.value ])

            if filter.operator == VectorStoreFilterOperator.NOT_IN:
                return metadata_value not in (filter.value if isinstance(filter.value, (list, tuple)) else [ filter.value ])

        if isinstance(filter, (list, tuple)):
            return all(self._evaluate_filter(metadata, item) for item in filter)

        return True

class FaissVectorStoreAction(VectorStoreAction):
    def __init__(self, config: VectorStoreActionConfig, index_manager: FaissIndexManager, lock: asyncio.Lock):
        super().__init__(config, index_manager)

        self.index_manager: FaissIndexManager = index_manager
        self.lock: asyncio.Lock = lock

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
        def _insert() -> Dict[str, Any]:
            count = self.index_manager.insert(
                vector_ids=vector_ids,
                vectors=vectors,
                metadatas=metadatas
            )

            return { "affected_rows": count, "status": "completed" }

        async with self.lock:
            return await self._run_in_executor(_insert)

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
        def _update() -> Dict[str, Any]:
            count = self.index_manager.update(
                vector_ids=vector_ids,
                vectors=vectors,
                metadatas=metadatas
            )

            return { "affected_rows": count, "status": "completed" }

        async with self.lock:
            return await self._run_in_executor(_update)

    async def _search(
        self,
        collection: Any,
        queries: List[List[float]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        def _search() -> List[List[Dict[str, Any]]]:
            return self.index_manager.search(
                queries=queries,
                top_k=int(params.get("top_k") or 10),
                filter=params.get("filter"),
                output_fields=params.get("output_fields")
            )

        async with self.lock:
            return await self._run_in_executor(_search)

    async def _delete(
        self,
        collection: Any,
        vector_ids: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        def _delete() -> Dict[str, Any]:
            count = self.index_manager.delete(
                vector_ids=vector_ids,
                filter=params.get("filter")
            )

            return { "affected_rows": count, "status": "completed" }

        async with self.lock:
            return await self._run_in_executor(_delete)

@register_vector_store_driver(VectorStoreDriverType.FAISS)
class FaissVectorStoreService(VectorStoreDriver):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.index_manager: FaissIndexManager = FaissIndexManager(
            dimension=self.config.dimension,
            metric=self.config.metric,
            storage_dir=self.config.storage_dir
        )
        self.lock: asyncio.Lock = asyncio.Lock()

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "faiss-cpu" ]

    async def _start(self) -> None:
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await FaissVectorStoreAction(action, self.index_manager, self.lock).run(context)
