from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VectorStoreDriver, VectorStoreDriverType, register_vector_store_driver
from ..base import ComponentActionContext
from .common import VectorStoreAction
import ulid

if TYPE_CHECKING:
    from pinecone import Pinecone

class PineconeFilterBuilder:
    def build(self, filter: Any) -> Optional[Dict[str, Any]]:
        if not filter:
            return None

        conditions = self._build_conditions(filter)

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return { "$and": conditions }

    def _build_conditions(self, filter: Any) -> List[Dict[str, Any]]:
        if isinstance(filter, (list, tuple, set)):
            conditions: List[Dict[str, Any]] = []

            for item in filter:
                item_conditions = self._build_conditions(item)
                conditions.extend(item_conditions)

            return conditions

        if isinstance(filter, dict):
            condition = VectorStoreFilterCondition.model_validate(filter)
            built = self._build_field_condition(condition)

            if built:
                return [ built ]

            return []

        return []

    def _build_field_condition(self, condition: VectorStoreFilterCondition) -> Optional[Dict[str, Any]]:
        field = condition.field
        val = condition.value
        op = condition.operator

        if op == VectorStoreFilterOperator.EQ:
            return { field: { "$eq": val } }

        if op == VectorStoreFilterOperator.NEQ:
            return { field: { "$ne": val } }

        if op == VectorStoreFilterOperator.GT:
            return { field: { "$gt": val } }

        if op == VectorStoreFilterOperator.GTE:
            return { field: { "$gte": val } }

        if op == VectorStoreFilterOperator.LT:
            return { field: { "$lt": val } }

        if op == VectorStoreFilterOperator.LTE:
            return { field: { "$lte": val } }

        if op == VectorStoreFilterOperator.IN:
            values = list(val) if isinstance(val, (list, tuple, set)) else [ val ]
            return { field: { "$in": values } }

        if op == VectorStoreFilterOperator.NOT_IN:
            values = list(val) if isinstance(val, (list, tuple, set)) else [ val ]
            return { field: { "$nin": values } }

        return None

class PineconeVectorStoreAction(VectorStoreAction):
    def __init__(self, config: VectorStoreActionConfig, client: Any, component_config: VectorStoreComponentConfig):
        super().__init__(config, client)

        self.component_config: VectorStoreComponentConfig = component_config

    def _resolve_index_name(self, collection: Any) -> str:
        index_name = getattr(self.config, "index_name", None)
        if not isinstance(index_name, str) or not index_name:
            index_name = collection
        if not isinstance(index_name, str) or not index_name:
            index_name = getattr(self.component_config, "index_name", None)

        if not isinstance(index_name, str) or not index_name:
            raise ValueError("Pinecone index_name must be specified in action config, collection parameter, or component config")

        return str(index_name)

    def _resolve_namespace(self) -> str:
        namespace = getattr(self.config, "namespace", None)
        if not isinstance(namespace, str):
            namespace = getattr(self.component_config, "namespace", None)
        if not isinstance(namespace, str):
            namespace = ""

        return str(namespace)

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
        index_name = self._resolve_index_name(collection)
        namespace = self._resolve_namespace()

        ids = [ str(vector_id) for vector_id in vector_ids ] if vector_ids is not None else [ str(ulid.new()) for _ in vectors ]
        meta_list = metadatas or [ {} for _ in vectors ]

        records = [
            {
                "id": str_id,
                "values": vector,
                "metadata": metadata or {}
            }
            for str_id, vector, metadata in zip(ids, vectors, meta_list)
        ]

        def _upsert() -> int:
            index = self.client.Index(index_name)
            index.upsert(vectors=records, namespace=namespace)
            return len(records)

        affected_rows = await self._run_in_executor(_upsert)

        return { "ids": ids, "affected_rows": affected_rows }

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
        index_name = self._resolve_index_name(collection)
        namespace = self._resolve_namespace()

        str_ids = [ str(vector_id) for vector_id in vector_ids ]

        def _update() -> int:
            index = self.client.Index(index_name)

            if vectors:
                records = []

                for index_idx, str_id in enumerate(str_ids):
                    vec = vectors[index_idx] if index_idx < len(vectors) else None
                    meta = metadatas[index_idx] if metadatas and index_idx < len(metadatas) else {}

                    if vec is not None:
                        record: Dict[str, Any] = { "id": str_id, "values": vec }

                        if meta:
                            record["metadata"] = meta

                        records.append(record)

                if records:
                    index.upsert(vectors=records, namespace=namespace)
            elif metadatas:
                for str_id, meta in zip(str_ids, metadatas):
                    if meta:
                        index.update(id=str_id, set_metadata=meta, namespace=namespace)

            return len(str_ids)

        affected_rows = await self._run_in_executor(_update)

        return { "affected_rows": affected_rows }

    async def _search(
        self,
        collection: Any,
        queries: List[List[float]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        index_name = self._resolve_index_name(collection)
        namespace = self._resolve_namespace()

        top_k = int(params.get("top_k") or 10)
        raw_filter = params.get("filter")
        output_fields = params.get("output_fields")

        query_filter = PineconeFilterBuilder().build(raw_filter)

        def _query() -> List[List[Dict[str, Any]]]:
            index = self.client.Index(index_name)
            results = []

            for query_vector in queries:
                response = index.query(
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True,
                    include_values=True,
                    filter=query_filter,
                    namespace=namespace
                )

                hits = []
                matches = response.get("matches", []) if isinstance(response, dict) else getattr(response, "matches", [])

                for match in matches:
                    match_id = match.get("id") if isinstance(match, dict) else getattr(match, "id", None)
                    match_score = match.get("score") if isinstance(match, dict) else getattr(match, "score", 0.0)
                    match_values = match.get("values") if isinstance(match, dict) else getattr(match, "values", None)
                    metadata = (match.get("metadata") if isinstance(match, dict) else getattr(match, "metadata", None)) or {}

                    if output_fields:
                        metadata = { field: metadata[field] for field in output_fields if field in metadata }

                    hits.append({
                        "id": match_id,
                        "score": float(match_score),
                        "vector": match_values,
                        "metadata": metadata
                    })

                results.append(hits)

            return results

        return await self._run_in_executor(_query)

    async def _delete(
        self,
        collection: Any,
        vector_ids: Optional[List[Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        index_name = self._resolve_index_name(collection)
        namespace = self._resolve_namespace()

        raw_filter = params.get("filter")
        query_filter = PineconeFilterBuilder().build(raw_filter)

        def _delete() -> int:
            index = self.client.Index(index_name)

            if vector_ids:
                str_ids = [ str(vector_id) for vector_id in vector_ids ]
                index.delete(ids=str_ids, namespace=namespace)
                return len(str_ids)

            if query_filter:
                index.delete(filter=query_filter, namespace=namespace)

            return 0

        affected_rows = await self._run_in_executor(_delete)

        return { "affected_rows": affected_rows }

@register_vector_store_driver(VectorStoreDriverType.PINECONE)
class PineconeVectorStoreService(VectorStoreDriver):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[Any] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pinecone-client" ]

    async def _start(self) -> None:
        from pinecone import Pinecone

        init_kwargs: Dict[str, Any] = {}

        if self.config.api_key:
            init_kwargs["api_key"] = self.config.api_key

        if self.config.environment:
            init_kwargs["environment"] = self.config.environment

        if hasattr(self.config, "pool_threads") and self.config.pool_threads:
            init_kwargs["pool_threads"] = self.config.pool_threads

        self.client = Pinecone(**init_kwargs)

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        self.client = None

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await PineconeVectorStoreAction(action, self.client, self.config).run(context)
