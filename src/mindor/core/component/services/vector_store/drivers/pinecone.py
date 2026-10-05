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
                conditions.extend(self._build_conditions(item))

            return conditions

        if isinstance(filter, dict):
            condition = VectorStoreFilterCondition.model_validate(filter)
            built = self._build_field_condition(condition)

            return [ built ] if built else []

        return []

    def _build_field_condition(self, condition: VectorStoreFilterCondition) -> Optional[Dict[str, Any]]:
        operator_map = {
            VectorStoreFilterOperator.EQ:  "$eq",
            VectorStoreFilterOperator.NEQ: "$ne",
            VectorStoreFilterOperator.GT:  "$gt",
            VectorStoreFilterOperator.GTE: "$gte",
            VectorStoreFilterOperator.LT:  "$lt",
            VectorStoreFilterOperator.LTE: "$lte",
        }

        operator = operator_map.get(condition.operator)

        if operator:
            return { condition.field: { operator: condition.value } }

        if condition.operator == VectorStoreFilterOperator.IN:
            values = list(condition.value) if isinstance(condition.value, (list, tuple, set)) else [ condition.value ]
            return { condition.field: { "$in": values } }

        if condition.operator == VectorStoreFilterOperator.NOT_IN:
            values = list(condition.value) if isinstance(condition.value, (list, tuple, set)) else [ condition.value ]
            return { condition.field: { "$nin": values } }

        return None

class PineconeVectorStoreAction(VectorStoreAction):
    def _resolve_namespace(self) -> Optional[str]:
        namespace = getattr(self.config, "namespace", None)

        if namespace:
            return namespace

        return None

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
            ids = [ str(vector_id) for vector_id in vector_ids ] if vector_ids is not None else [ str(ulid.new()) for _ in vectors ]
            meta_list = metadatas or [ {} for _ in vectors ]

            records = [
                { "id": id, "values": vector, "metadata": metadata or {} }
                for id, vector, metadata in zip(ids, vectors, meta_list)
            ]

            index = self.client.Index(collection)
            index.upsert(vectors=records, namespace=self._resolve_namespace())

            return { "ids": ids, "affected_rows": len(ids) }

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
            namespace = self._resolve_namespace()
            ids = [ str(vector_id) for vector_id in vector_ids ]
            index = self.client.Index(collection)

            if vectors:
                records = []

                for position, id in enumerate(ids):
                    vector   = vectors[position] if position < len(vectors) else None
                    metadata = metadatas[position] if metadatas and position < len(metadatas) else {}

                    if vector is not None:
                        record: Dict[str, Any] = { "id": id, "values": vector }

                        if metadata:
                            record["metadata"] = metadata

                        records.append(record)

                if records:
                    index.upsert(vectors=records, namespace=namespace)
            elif metadatas:
                for id, metadata in zip(ids, metadatas):
                    if metadata:
                        index.update(id=id, set_metadata=metadata, namespace=namespace)

            return { "affected_rows": len(ids) }

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
            top_k         = params["top_k"]
            filter        = params["filter"]
            output_fields = params["output_fields"]
            namespace     = self._resolve_namespace()

            query_filter = PineconeFilterBuilder().build(filter)
            index = self.client.Index(collection)
            results = []

            for query_vector in queries:
                response = index.query(
                    vector=query_vector,
                    top_k=int(top_k),
                    include_metadata=True,
                    include_values=True,
                    filter=query_filter,
                    namespace=namespace
                )

                matches = response.get("matches", []) if isinstance(response, dict) else getattr(response, "matches", [])
                hits = []

                for match in matches:
                    id       = match.get("id") if isinstance(match, dict) else getattr(match, "id", None)
                    score    = match.get("score") if isinstance(match, dict) else getattr(match, "score", 0.0)
                    vector   = match.get("values") if isinstance(match, dict) else getattr(match, "values", None)
                    metadata = (match.get("metadata") if isinstance(match, dict) else getattr(match, "metadata", None)) or {}

                    if output_fields:
                        metadata = { key: metadata[key] for key in output_fields if key in metadata }

                    hits.append({
                        "id":       id,
                        "score":    float(score) if score is not None else 0.0,
                        "vector":   vector,
                        "metadata": metadata
                    })

                results.append(hits)

            return results

        return await self._run_in_executor(_search)

    async def _delete(
        self,
        collection: Any,
        vector_ids: Optional[List[Any]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        def _delete() -> Dict[str, Any]:
            namespace = self._resolve_namespace()
            index = self.client.Index(collection)

            if vector_ids:
                ids = [ str(vector_id) for vector_id in vector_ids ]
                index.delete(ids=ids, namespace=namespace)
                return { "affected_rows": len(ids) }

            query_filter = PineconeFilterBuilder().build(params["filter"])

            if query_filter:
                index.delete(filter=query_filter, namespace=namespace)

            return { "affected_rows": 0 }

        return await self._run_in_executor(_delete)

@register_vector_store_driver(VectorStoreDriverType.PINECONE)
class PineconeVectorStoreService(VectorStoreDriver):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[Pinecone] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pinecone" ]

    async def _start(self) -> None:
        from pinecone import Pinecone

        init_kwargs: Dict[str, Any] = {}

        if self.config.api_key:
            init_kwargs["api_key"] = self.config.api_key

        if self.config.environment:
            init_kwargs["environment"] = self.config.environment

        if self.config.pool_threads:
            init_kwargs["pool_threads"] = self.config.pool_threads

        self.client = Pinecone(**init_kwargs)

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client:
            self.client = None

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await PineconeVectorStoreAction(action, self.client).run(context)
