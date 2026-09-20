from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VectorStoreDriver, VectorStoreDriverType, register_vector_store_driver
from ..base import ComponentActionContext
from .common import VectorStoreAction
import ulid

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient

class QdrantFilterSpecBuilder:
    def build(self, filter: Any) -> Optional[Any]:
        from qdrant_client.http import models as qmodels

        must, must_not = self._build_conditions(filter)

        if not must and not must_not:
            return None

        return qmodels.Filter(
            must=must or None,
            must_not=must_not or None
        )

    def _build_conditions(self, filter: Any) -> tuple[List[Any], List[Any]]:
        must: List[Any] = []
        must_not: List[Any] = []

        if isinstance(filter, (list, tuple, set)):
            for item in filter:
                item_must, item_must_not = self._build_conditions(item)
                must.extend(item_must)
                must_not.extend(item_must_not)

            return must, must_not

        if isinstance(filter, dict):
            for field, value in filter.items():
                must.append(self._build_field_condition(field, value))

            return must, must_not

        if isinstance(filter, VectorStoreFilterCondition):
            condition, is_negated = self._build_operator_condition(filter)

            if condition is not None:
                (must_not if is_negated else must).append(condition)

            return must, must_not

        return must, must_not

    def _build_field_condition(self, field: str, value: Any) -> Any:
        from qdrant_client.http import models as qmodels

        if isinstance(value, (list, tuple, set)):
            return qmodels.FieldCondition(key=field, match=qmodels.MatchAny(any=list(value)))

        return qmodels.FieldCondition(key=field, match=qmodels.MatchValue(value=value))

    def _build_operator_condition(self, condition: VectorStoreFilterCondition) -> tuple[Optional[Any], bool]:
        from qdrant_client.http import models as qmodels

        if condition.operator == VectorStoreFilterOperator.EQ:
            return qmodels.FieldCondition(key=condition.field, match=qmodels.MatchValue(value=condition.value)), False

        if condition.operator == VectorStoreFilterOperator.NEQ:
            return qmodels.FieldCondition(key=condition.field, match=qmodels.MatchValue(value=condition.value)), True

        if condition.operator == VectorStoreFilterOperator.GT:
            return qmodels.FieldCondition(key=condition.field, range=qmodels.Range(gt=condition.value)), False

        if condition.operator == VectorStoreFilterOperator.GTE:
            return qmodels.FieldCondition(key=condition.field, range=qmodels.Range(gte=condition.value)), False

        if condition.operator == VectorStoreFilterOperator.LT:
            return qmodels.FieldCondition(key=condition.field, range=qmodels.Range(lt=condition.value)), False

        if condition.operator == VectorStoreFilterOperator.LTE:
            return qmodels.FieldCondition(key=condition.field, range=qmodels.Range(lte=condition.value)), False

        if condition.operator == VectorStoreFilterOperator.IN:
            values = list(condition.value) if isinstance(condition.value, (list, tuple, set)) else [ condition.value ]
            return qmodels.FieldCondition(key=condition.field, match=qmodels.MatchAny(any=values)), False

        if condition.operator == VectorStoreFilterOperator.NOT_IN:
            values = list(condition.value) if isinstance(condition.value, (list, tuple, set)) else [ condition.value ]
            return qmodels.FieldCondition(key=condition.field, match=qmodels.MatchAny(any=values)), True

        return None, False

class QdrantVectorStoreAction(VectorStoreAction):
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
        from qdrant_client.http import models as qmodels

        ids = vector_ids if vector_ids is not None else [ str(ulid.new()) for _ in vectors ]

        points = [
            qmodels.PointStruct(id=id, vector=vector, payload=metadata or {})
            for id, vector, metadata in zip(ids, vectors, metadatas or [ {} for _ in vectors ])
        ]

        await self.client.upsert(
            collection_name=collection,
            points=points,
            wait=True
        )

        return { "ids": ids, "affected_rows": len(ids) }

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
        from qdrant_client.http import models as qmodels

        points = []

        for index, vector_id in enumerate(vector_ids):
            vector   = vectors[index] if vectors and index < len(vectors) else None
            metadata = metadatas[index] if metadatas and index < len(metadatas) else {}

            if vector is not None:
                points.append(qmodels.PointStruct(id=vector_id, vector=vector, payload=metadata))

        if points:
            await self.client.upsert(
                collection_name=collection,
                points=points,
                wait=True
            )
        elif metadatas:
            for vector_id, metadata in zip(vector_ids, metadatas):
                await self.client.set_payload(
                    collection_name=collection,
                    payload=metadata,
                    points=[ vector_id ],
                    wait=True
                )

        return { "affected_rows": len(vector_ids) }

    async def _search(
        self,
        collection: Any,
        queries: List[List[float]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        top_k         = params["top_k"]
        filter        = params["filter"]
        output_fields = params["output_fields"]

        query_filter = QdrantFilterSpecBuilder().build(filter)

        results = []

        for query_vector in queries:
            hits_raw = await self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=int(top_k),
                with_payload=True,
                with_vectors=True
            )

            hits = []
            for hit in hits_raw:
                metadata = hit.payload or {}

                if output_fields:
                    metadata = { key: metadata[key] for key in output_fields if key in metadata }

                hits.append({
                    "id":       hit.id,
                    "score":    hit.score,
                    "vector":   hit.vector,
                    "metadata": metadata
                })
            results.append(hits)

        return results

    async def _delete(
        self,
        collection: Any,
        vector_ids: List[Any],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        from qdrant_client.http import models as qmodels

        filter = params["filter"]

        if vector_ids:
            await self.client.delete(
                collection_name=collection,
                points_selector=qmodels.PointIdsList(points=vector_ids),
                wait=True
            )
            return { "affected_rows": len(vector_ids) }

        if filter:
            await self.client.delete(
                collection_name=collection,
                points_selector=qmodels.FilterSelector(filter=QdrantFilterSpecBuilder().build(filter)),
                wait=True
            )

        return { "affected_rows": 0 }

@register_vector_store_driver(VectorStoreDriverType.QDRANT)
class QdrantVectorStoreService(VectorStoreDriver):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[AsyncQdrantClient] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "qdrant-client" ]

    async def _start(self) -> None:
        from qdrant_client import AsyncQdrantClient

        self.client = AsyncQdrantClient(**self._resolve_connection_params())

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client:
            await self.client.close()
            self.client = None

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await QdrantVectorStoreAction(action, self.client).run(context)

    def _resolve_connection_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        if self.config.url:
            params["url"] = self.config.url
        else:
            params["host"]         = self.config.host
            params["port"]         = self.config.grpc_port if self.config.prefer_grpc else self.config.port
            params["https"]        = self.config.https
            params["prefer_grpc"]  = self.config.prefer_grpc

        if self.config.api_key:
            params["api_key"] = self.config.api_key

        if self.config.prefix:
            params["prefix"] = self.config.prefix

        if self.config.timeout:
            params["timeout"] = parse_time(self.config.timeout)

        return params
