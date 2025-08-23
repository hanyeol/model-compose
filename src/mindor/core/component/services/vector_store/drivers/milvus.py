from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from typing import TYPE_CHECKING
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, MilvusVectorStoreActionConfig, VectorStoreActionMethod, VectorStoreFilterCondition, VectorStoreFilterOperator
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ..base import VectorStoreService, VectorStoreDriver, register_vector_store_service
from ..base import ComponentActionContext

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

class MilvusVectorStoreAction:
    def __init__(self, config: MilvusVectorStoreActionConfig):
        self.config: MilvusVectorStoreActionConfig = config

    async def run(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Any:
        result = await self._dispatch(context, client)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        if self.config.method == VectorStoreActionMethod.INSERT:
            return await self._insert(context, client)

        if self.config.method == VectorStoreActionMethod.UPDATE:
            return await self._update(context, client)

        if self.config.method == VectorStoreActionMethod.SEARCH:
            return await self._search(context, client)

        if self.config.method == VectorStoreActionMethod.DELETE:
            return await self._delete(context, client)

        raise ValueError(f"Unsupported vector action method: {self.config.method}")

    async def _insert(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        collection_name = await context.render_variable(self.config.collection)
        partition_name  = await context.render_variable(self.config.partition)
        vector          = await context.render_variable(self.config.vector)
        vector_id       = await context.render_variable(self.config.vector_id)
        metadata        = await context.render_variable(self.config.metadata)
        batch_size      = await context.render_variable(self.config.batch_size)

        is_single_input: bool = bool(not (isinstance(vector, list) and vector and isinstance(vector[0], (list, tuple))))
        vectors: List[List[float]] = [ vector ] if is_single_input else vector
        vector_ids: Optional[List[Union[int, str]]] = [ vector_id ] if is_single_input and vector_id else vector_id
        metadatas: Optional[List[Dict[str, Any]] ]= [ metadata ] if is_single_input and metadata else metadata
        batch_size = batch_size if batch_size and batch_size > 0 else len(vectors)
        inserted_ids, affected_rows = [], 0

        data = []
        for index, vector in enumerate(vectors):
            item = { self.config.vector_field: vector }

            if vector_ids and index < len(vector_ids):
                item.update({ self.config.id_field: vector_ids[index]})

            if metadatas and index < len(metadatas):
                item.update(metadatas[index])

            data.append(item)
        
        for index in range(0, len(data), batch_size):
            batch_data = data[index:index + batch_size]

            result = await client.insert(
                collection_name=collection_name,
                partition_name=partition_name,
                data=batch_data
            )
            inserted_ids.extend(result["ids"])
            affected_rows += result["insert_count"]

        return { "ids": inserted_ids, "affected_rows": affected_rows }

    async def _update(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        collection_name = await context.render_variable(self.config.collection)
        partition_name  = await context.render_variable(self.config.partition)
        vector_id       = await context.render_variable(self.config.vector_id)
        vector          = await context.render_variable(self.config.vector)
        metadata        = await context.render_variable(self.config.metadata)
        batch_size      = await context.render_variable(self.config.batch_size)

        is_single_input: bool = bool(not isinstance(vector_id, list))
        vector_ids: List[Union[int, str]] = [ vector_id ] if is_single_input else vector_id
        vectors: Optional[List[List[float]]] = [ vector ] if is_single_input and vector else vector
        metadatas: Optional[List[Dict[str, Any]]] = [ metadata ] if is_single_input and metadata else metadata
        batch_size = batch_size if batch_size and batch_size > 0 else len(vector_ids)
        affected_rows = 0

        data = []
        for index, vector_id in enumerate(vector_ids):
            item = { self.config.id_field: vector_id }

            if vectors and index < len(vectors):
                item.update({ self.config.vector_field: vectors[index] })

            if metadatas and index < len(metadatas):
                item.update(metadatas[index])

            data.append(item)

        for index in range(0, len(data), batch_size):
            batch_data = data[index:index + batch_size]
            batch_vector_ids = vector_ids[index:index + batch_size]

            if not self.config.insert_if_not_exist:
                filter_expr = MilvusFilterExpressionBuilder().build({ self.config.id_field: batch_vector_ids })

                result = await client.query(
                    collection_name=collection_name,
                    partition_names=[ partition_name ] if partition_name else None,
                    expr=filter_expr,
                    output_fields=[ self.config.id_field ]
                )

                found_ids = { row[self.config.id_field] for row in (result or []) }
                missing_ids = set(batch_vector_ids) - found_ids
                if missing_ids:
                    batch_data = [ item for item in batch_data if item[self.config.id_field] in found_ids ]

            if len(data) > 0:
                result = await client.upsert(
                    collection_name=collection_name,
                    partition_name=partition_name,
                    data=batch_data
                )
                affected_rows += result["upsert_count"]

        return { "affected_rows": affected_rows }

    async def _search(self, context: ComponentActionContext, client: AsyncMilvusClient) -> List[List[Dict[str, Any]]] | List[Dict[str, Any]]:
        collection_name = await context.render_variable(self.config.collection)
        partition_names = await context.render_variable(self.config.partitions)
        query           = await context.render_variable(self.config.query)
        top_k           = await context.render_variable(self.config.top_k)
        filter          = await context.render_variable(self.config.filter)
        output_fields   = await context.render_variable(self.config.output_fields)
        batch_size      = await context.render_variable(self.config.batch_size)

        is_single_input: bool = bool(not (isinstance(query, list) and query and isinstance(query[0], (list, tuple))))
        queries: List[List[float]] = [ query ] if is_single_input else query
        filter_expr = MilvusFilterExpressionBuilder().build(filter)
        search_params = await self._resolve_search_params(context)
        batch_size = batch_size if batch_size and batch_size > 0 else len(queries)
        results = []

        for index in range(0, len(queries), batch_size):
            batch_queries = queries[index:index + batch_size]
        
            result = await client.search(
                collection_name=collection_name,
                partition_names=partition_names,
                data=batch_queries,
                filter=filter_expr,
                limit=top_k,
                output_fields=output_fields or None,
                search_params=search_params or None
            )
            for n in range(len(result)):
                hits = []
                for hit in result[n]:
                    hits.append({
                        "id": hit["id"],
                        "score": 1 / (1 + hit["distance"]),
                        "distance": hit["distance"],
                        "metadata": hit["entity"]
                    })
                results.append(hits)

        return results[0] if is_single_input else results

    async def _delete(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        collection_name = await context.render_variable(self.config.collection)
        partition_name  = await context.render_variable(self.config.partition)
        vector_id       = await context.render_variable(self.config.vector_id)
        filter          = await context.render_variable(self.config.filter)
        batch_size      = await context.render_variable(self.config.batch_size)

        is_single_input: bool = bool(not isinstance(vector_id, list))
        vector_ids: List[Union[int, str]] = [ vector_id ] if is_single_input else vector_id
        batch_size = batch_size if batch_size and batch_size > 0 else len(vector_ids)
        affected_rows = 0

        for index in range(0, len(vector_ids), batch_size):
            batch_vector_ids = vector_ids[index:index + batch_size]
            filter_expr = MilvusFilterExpressionBuilder().build([ { self.config.id_field: batch_vector_ids }, filter ])

            result = await client.delete(
                collection_name=collection_name,
                partition_name=partition_name,
                filter=filter_expr
            )
            affected_rows += result["delete_count"]

        return { "affected_rows": affected_rows }

    async def _resolve_search_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        search_params = {}

        metric_type = await context.render_variable(self.config.metric_type)
        if metric_type:
            search_params["metric_type"] = metric_type

        return search_params

@register_vector_store_service(VectorStoreDriver.MILVUS)
class MilvusVectorStoreService(VectorStoreService):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.client: Optional[AsyncMilvusClient] = None

    async def _serve(self) -> None:
        from pymilvus import AsyncMilvusClient

        self.client = AsyncMilvusClient(
            **self._resolve_connection_params(),
            user=self.config.user or "",
            password=self.config.password or "",
            db_name=self.config.database or "",
            timeout=self.config.timeout
        )

    async def _shutdown(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None

    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await MilvusVectorStoreAction(action).run(context, self.client)

    def _resolve_connection_params(self) -> Dict[str, Any]:
        if self.config.endpoint:
            return { "uri": self.config.endpoint }

        if self.config.protocol not in [ "grpc", "grpcs" ]:
            return { "uri": f"{self.config.protocol}://{self.config.host}:{self.config.port}" }
        
        return { "host": self.config.host, "port": self.config.port, "secure": bool(self.config.protocol == "grpcs")  }
