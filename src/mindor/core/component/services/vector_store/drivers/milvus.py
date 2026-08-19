from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from mindor.dsl.schema.action import VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.cancellation import CancellationToken
from ..base import VectorStoreService, VectorStoreDriver, register_vector_store_service
from ..base import ComponentActionContext
from .common import VectorStoreAction

if TYPE_CHECKING:
    from pymilvus import AsyncMilvusClient

class MilvusFilterExpressionBuilder:
    def build(self, filter: Any) -> Optional[str]:
        clauses: List[str] = self._build_clauses(filter)

        if not clauses:
            return None

        return " and ".join(clauses)

    def _build_clauses(self, filter: Any) -> List[str]:
        clauses: List[str] = []

        if isinstance(filter, (list, tuple, set)):
            for item in filter:
                clauses.extend(self._build_clauses(item))
            return clauses

        if isinstance(filter, dict):
            for field, value in filter.items():
                clause = self._format_field_clause(field, value)
                if clause:
                    clauses.append(clause)
            return clauses

        if isinstance(filter, VectorStoreFilterCondition):
            clause = self._format_condition(filter)
            if clause:
                clauses.append(clause)
            return clauses

        if isinstance(filter, str):
            clause = filter.strip()
            if clause:
                clauses.append(clause)
            return clauses

        return clauses

    def _format_condition(self, condition: VectorStoreFilterCondition) -> Optional[str]:
        if condition.operator == VectorStoreFilterOperator.EQ:
            return f"{condition.field} == {self._format_scalar(condition.value)}"

        if condition.operator == VectorStoreFilterOperator.NEQ:
            return f"{condition.field} != {self._format_scalar(condition.value)}"

        if condition.operator == VectorStoreFilterOperator.GT:
            return f"{condition.field} > {self._format_scalar(condition.value)}"

        if condition.operator == VectorStoreFilterOperator.GTE:
            return f"{condition.field} >= {self._format_scalar(condition.value)}"

        if condition.operator == VectorStoreFilterOperator.LT:
            return f"{condition.field} < {self._format_scalar(condition.value)}"

        if condition.operator == VectorStoreFilterOperator.LTE:
            return f"{condition.field} <= {self._format_scalar(condition.value)}"

        if condition.operator == VectorStoreFilterOperator.IN:
            return f"{condition.field} in {self._format_list(condition.value)}"

        if condition.operator == VectorStoreFilterOperator.NOT_IN:
            return f"{condition.field} not in {self._format_list(condition.value)}"

        return None

    def _format_field_clause(self, field: str, value: Any) -> Optional[str]:
        if isinstance(value, (list, tuple, set)):
            return f"{field} in {self._format_list(list(value))}" if value else None

        if not isinstance(value, dict):
            return f"{field} == {self._format_scalar(value)}"

        return None

    def _format_list(self, value: List[Any]) -> str:
        return "[ " + ", ".join(self._format_scalar(item) for item in value) + " ]"

    def _format_scalar(self, value: Any) -> str:
        if isinstance(value, str):
            return "'" + value.replace("'", "\\'") + "'"

        if isinstance(value, bool):
            return "true" if value else "false"

        if value is None:
            return "null"

        return str(value)

class MilvusVectorStoreAction(VectorStoreAction):
    async def _resolve_collection(self, method: VectorStoreActionMethod, context: ComponentActionContext) -> Any:
        collection = await super()._resolve_collection(method, context)

        if method == VectorStoreActionMethod.SEARCH:
            partitions = await context.render_variable(self.config.partitions)

            return (collection, partitions)

        partition = await context.render_variable(self.config.partition)

        return (collection, partition)

    async def _resolve_params(self, method: VectorStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(method, context)

        if method == VectorStoreActionMethod.SEARCH:
            search_params = await self._resolve_search_params(context)

            params.update({
                "search_params": search_params
            })

            return params

        return params

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
        collection_name, partition_name = collection
        id_field     = params["id_field"]
        vector_field = params["vector_field"]

        data = []
        for index, vector in enumerate(vectors):
            item = { vector_field: vector }

            if vector_ids and index < len(vector_ids):
                item[id_field] = vector_ids[index]

            if metadatas and index < len(metadatas):
                item.update(metadatas[index])

            data.append(item)

        result = await self.client.insert(
            collection_name=collection_name,
            partition_name=partition_name,
            data=data
        )

        return { "ids": result["ids"], "affected_rows": result["insert_count"] }

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
        collection_name, partition_name = collection
        id_field            = params["id_field"]
        vector_field        = params["vector_field"]
        insert_if_not_exist = params["insert_if_not_exist"]

        data = []
        for index, vector_id in enumerate(vector_ids):
            item = { id_field: vector_id }

            if vectors and index < len(vectors):
                item[vector_field] = vectors[index]

            if metadatas and index < len(metadatas):
                item.update(metadatas[index])

            data.append(item)

        if not insert_if_not_exist:
            filter_expr = MilvusFilterExpressionBuilder().build({ id_field: vector_ids })

            existing = await self.client.query(
                collection_name=collection_name,
                partition_names=[ partition_name ] if partition_name else None,
                expr=filter_expr,
                output_fields=[ id_field ]
            )

            found_ids = { row[id_field] for row in (existing or []) }
            data = [ item for item in data if item[id_field] in found_ids ]

        if not data:
            return { "affected_rows": 0 }

        result = await self.client.upsert(
            collection_name=collection_name,
            partition_name=partition_name,
            data=data
        )

        return { "affected_rows": result["upsert_count"] }

    async def _search(
        self,
        collection: Any,
        queries: List[List[float]],
        *,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> List[List[Dict[str, Any]]]:
        collection_name, partition_names = collection
        vector_field  = params["vector_field"]
        top_k         = params["top_k"]
        filter        = params["filter"]
        output_fields = params["output_fields"]
        search_params = params["search_params"]

        filter_expr = MilvusFilterExpressionBuilder().build(filter)

        result = await self.client.search(
            collection_name=collection_name,
            partition_names=partition_names,
            data=queries,
            anns_field=vector_field,
            filter=filter_expr,
            limit=top_k,
            output_fields=output_fields or None,
            search_params=search_params or None
        )

        results = []

        for query in range(len(result)):
            hits = []
            for hit in result[query]:
                hits.append({
                    "id": hit["id"],
                    "score": 1 / (1 + hit["distance"]),
                    "distance": hit["distance"],
                    "metadata": hit["entity"]
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
        collection_name, partition_name = collection
        id_field = params["id_field"]
        filter   = params["filter"]

        filter_expr = MilvusFilterExpressionBuilder().build([ { id_field: vector_ids }, filter ])

        result = await self.client.delete(
            collection_name=collection_name,
            partition_name=partition_name,
            filter=filter_expr
        )

        return { "affected_rows": result["delete_count"] }

    async def _resolve_search_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        metric_type = await context.render_variable(self.config.metric_type)

        params: Dict[str, Any] = {}

        if metric_type:
            params["metric_type"] = metric_type

        return params

@register_vector_store_service(VectorStoreDriver.MILVUS)
class MilvusVectorStoreService(VectorStoreService):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[AsyncMilvusClient] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pymilvus" ]

    async def _start(self) -> None:
        from pymilvus import AsyncMilvusClient

        self.client = AsyncMilvusClient(
            **self._resolve_connection_params(),
            user=self.config.user or "",
            password=self.config.password or "",
            db_name=self.config.database or "",
            timeout=parse_time(self.config.timeout)
        )

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        if self.client:
            await self.client.close()
            self.client = None

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await MilvusVectorStoreAction(action, self.client).run(context)

    def _resolve_connection_params(self) -> Dict[str, Any]:
        if self.config.endpoint:
            return { "uri": self.config.endpoint }

        if self.config.protocol not in [ "grpc", "grpcs" ]:
            return { "uri": f"{self.config.protocol}://{self.config.host}:{self.config.port}" }

        return { "host": self.config.host, "port": self.config.port, "secure": bool(self.config.protocol == "grpcs")  }
