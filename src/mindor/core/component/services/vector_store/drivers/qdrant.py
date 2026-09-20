from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any, Union
import ulid, os

from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VectorStoreDriver, VectorStoreDriverType, register_vector_store_driver
from ..base import ComponentActionContext
from .common import VectorStoreAction

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http import models as qmodels


def _get_qmodels() -> Any:
    try:
        from qdrant_client.http import models as qmodels
        return qmodels
    except ImportError:
        return None


class QdrantFilterSpecBuilder:
    """Builds Qdrant filter structures from VectorStoreFilterCondition objects, dicts, or lists."""

    def build(self, filter: Any) -> Any:
        qmodels = _get_qmodels()

        if not filter:
            return None

        conditions = self._build_conditions(filter, qmodels)
        if not conditions:
            return None

        if qmodels:
            must_conditions = []
            must_not_conditions = []
            for cond in conditions:
                if isinstance(cond, dict) and cond.get("_is_must_not"):
                    must_not_conditions.append(cond["condition"])
                else:
                    must_conditions.append(cond)
            return qmodels.Filter(
                must=must_conditions if must_conditions else None,
                must_not=must_not_conditions if must_not_conditions else None,
            )

        return conditions

    def _build_conditions(self, filter: Any, qmodels: Any) -> List[Any]:
        conditions: List[Any] = []

        if isinstance(filter, (list, tuple, set)):
            for item in filter:
                conditions.extend(self._build_conditions(item, qmodels))
            return conditions

        if isinstance(filter, dict):
            for field, value in filter.items():
                if qmodels:
                    if isinstance(value, (list, tuple, set)):
                        conditions.append(
                            qmodels.FieldCondition(
                                key=field,
                                match=qmodels.MatchAny(any=list(value)),
                            )
                        )
                    else:
                        conditions.append(
                            qmodels.FieldCondition(
                                key=field,
                                match=qmodels.MatchValue(value=value),
                            )
                        )
                else:
                    conditions.append({field: value})
            return conditions

        if isinstance(filter, VectorStoreFilterCondition):
            cond = self._format_condition(filter, qmodels)
            if cond is not None:
                conditions.append(cond)
            return conditions

        return conditions

    def _format_condition(self, condition: VectorStoreFilterCondition, qmodels: Any) -> Any:
        field = condition.field
        op = condition.operator
        val = condition.value

        if not qmodels:
            return {field: {op.value: val}}

        if op == VectorStoreFilterOperator.EQ:
            return qmodels.FieldCondition(key=field, match=qmodels.MatchValue(value=val))

        if op == VectorStoreFilterOperator.NEQ:
            return {
                "_is_must_not": True,
                "condition": qmodels.FieldCondition(key=field, match=qmodels.MatchValue(value=val)),
            }

        if op == VectorStoreFilterOperator.GT:
            return qmodels.FieldCondition(key=field, range=qmodels.Range(gt=val))

        if op == VectorStoreFilterOperator.GTE:
            return qmodels.FieldCondition(key=field, range=qmodels.Range(gte=val))

        if op == VectorStoreFilterOperator.LT:
            return qmodels.FieldCondition(key=field, range=qmodels.Range(lt=val))

        if op == VectorStoreFilterOperator.LTE:
            return qmodels.FieldCondition(key=field, range=qmodels.Range(lte=val))

        if op == VectorStoreFilterOperator.IN:
            val_list = list(val) if isinstance(val, (list, tuple, set)) else [val]
            return qmodels.FieldCondition(key=field, match=qmodels.MatchAny(any=val_list))

        if op == VectorStoreFilterOperator.NOT_IN:
            val_list = list(val) if isinstance(val, (list, tuple, set)) else [val]
            return {
                "_is_must_not": True,
                "condition": qmodels.FieldCondition(key=field, match=qmodels.MatchAny(any=val_list)),
            }

        return None


class QdrantVectorStoreAction(VectorStoreAction):
    def __init__(self, config: VectorStoreActionConfig, client: Any):
        super().__init__(config, client)

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
        qmodels = _get_qmodels()

        count = len(vectors)
        if not vector_ids:
            vector_ids = [str(ulid.new()) for _ in range(count)]
        if not metadatas:
            metadatas = [{} for _ in range(count)]

        points = []
        for vid, vec, meta in zip(vector_ids, vectors, metadatas):
            if qmodels:
                point = qmodels.PointStruct(id=vid, vector=vec, payload=meta or {})
            else:
                point = {"id": vid, "vector": vec, "payload": meta or {}}
            points.append(point)

        res = await self.client.upsert(
            collection_name=collection,
            points=points,
            wait=True,
        )

        return {
            "affected_rows": count,
            "status": getattr(res, "status", "completed"),
        }

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
        qmodels = _get_qmodels()

        count = len(vector_ids)
        points = []

        for i, vid in enumerate(vector_ids):
            vec = vectors[i] if vectors and i < len(vectors) else None
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}

            if vec is not None:
                if qmodels:
                    point = qmodels.PointStruct(id=vid, vector=vec, payload=meta)
                else:
                    point = {"id": vid, "vector": vec, "payload": meta}
                points.append(point)

        if points:
            res = await self.client.upsert(
                collection_name=collection,
                points=points,
                wait=True,
            )
            status = getattr(res, "status", "completed")
        elif metadatas:
            for vid, meta in zip(vector_ids, metadatas):
                await self.client.set_payload(
                    collection_name=collection,
                    payload=meta,
                    points=[vid],
                    wait=True,
                )
            status = "completed"
        else:
            status = "noop"

        return {
            "affected_rows": count,
            "status": status,
        }

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

        qfilter = QdrantFilterSpecBuilder().build(filter_spec)

        results = []
        for query_vec in queries:
            search_res = await self.client.search(
                collection_name=collection,
                query_vector=query_vec,
                limit=top_k,
                query_filter=qfilter,
                with_payload=True,
                with_vectors=True,
            )

            hits = []
            for hit in search_res:
                payload = getattr(hit, "payload", {}) or {}
                if output_fields:
                    payload = {k: payload[k] for k in output_fields if k in payload}

                hits.append({
                    "id": getattr(hit, "id"),
                    "score": getattr(hit, "score"),
                    "vector": getattr(hit, "vector", None),
                    "metadata": payload,
                    "payload": payload,
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
        qmodels = _get_qmodels()
        filter_spec = params.get("filter")

        if vector_ids:
            selector = qmodels.PointIdsList(points=vector_ids) if qmodels else vector_ids
            res = await self.client.delete(
                collection_name=collection,
                points_selector=selector,
                wait=True,
            )
            affected = len(vector_ids)
        elif filter_spec:
            qfilter = QdrantFilterSpecBuilder().build(filter_spec)
            selector = qmodels.FilterSelector(filter=qfilter) if qmodels else qfilter
            res = await self.client.delete(
                collection_name=collection,
                points_selector=selector,
                wait=True,
            )
            affected = getattr(res, "affected_rows", 1)
        else:
            affected = 0

        return {"affected_rows": affected}


@register_vector_store_driver(VectorStoreDriverType.QDRANT)
class QdrantVectorStoreService(VectorStoreDriver):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)
        self.client: Optional[AsyncQdrantClient] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return ["qdrant-client"]

    async def _start(self) -> None:
        from qdrant_client import AsyncQdrantClient

        params = self._resolve_connection_params()
        self.client = AsyncQdrantClient(**params)
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

        if getattr(self.config, "url", None):
            params["url"] = self.config.url
        else:
            host = getattr(self.config, "host", "localhost")
            port = getattr(self.config, "port", 6333)
            grpc_port = getattr(self.config, "grpc_port", 6334)
            https = getattr(self.config, "https", False)
            prefer_grpc = getattr(self.config, "prefer_grpc", False)

            params["host"] = host
            params["port"] = grpc_port if prefer_grpc else port
            params["https"] = https
            params["prefer_grpc"] = prefer_grpc

        if getattr(self.config, "api_key", None):
            params["api_key"] = self.config.api_key

        if getattr(self.config, "prefix", None):
            params["prefix"] = self.config.prefix

        if getattr(self.config, "timeout", None):
            params["timeout"] = parse_time(self.config.timeout)

        return params
