from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from typing import TYPE_CHECKING
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, MilvusVectorStoreActionConfig, VectorStoreActionMethod
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ..base import VectorStoreService, VectorStoreDriver, register_vector_store_service
from ..base import ComponentActionContext
import json

if TYPE_CHECKING:
    from pymilvus import AsyncMilvusClient

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

        if self.config.method == VectorStoreActionMethod.REMOVE:
            return await self._remove(context, client)

        raise ValueError(f"Unsupported vector action method: {self.config.method}")

    async def _insert(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        vector   = await context.render_variable(self.config.vector)
        metadata = await context.render_variable(self.config.metadata)

        is_single_input: bool = True if not (isinstance(vector, list) and vector and isinstance(vector[0], (list, tuple))) else False
        vectors: List[List[float]] = [ vector ] if is_single_input else vector
        metadata: List[Dict[str, Any]] = [ metadata ] if is_single_input and metadata else metadata

        data = []
        for index, vector in enumerate(vectors):
            item = { self.config.vector_field: vector }

            if metadata and index < len(metadata):
                item.update(metadata[index])

            data.append(item)

        result = await client.insert(
            collection_name=self.config.collection_name,
            data=data,
            partition_name=self.config.partition_name
        )

        return { "ids": list(result["ids"]), "affected_rows": result["insert_count"] }

    async def _update(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        vector_id = await context.render_variable(self.config.vector_id)
        vector    = await context.render_variable(self.config.vector)
        metadata  = await context.render_variable(self.config.metadata)

        is_single_input: bool = True if not isinstance(vector_id, list) else False
        vector_ids: List[Union[int, str]] = [ vector_id ] if is_single_input else vector_id
        vectors: List[List[float]] = [ vector ] if is_single_input and vector else vector
        metadata: List[Dict[str, Any]] = [ metadata ] if is_single_input and metadata else metadata

        data = []
        for index, vector_id in enumerate(vector_ids):
            item = { self.config.id_field: vector_id }

            if vectors and index < len(vectors):
                item.update({ self.config.vector_field: vectors[index] })

            if metadata and index < len(metadata):
                item.update(metadata[index])

            data.append(item)

        if not self.config.insert_if_not_exist:
            queried = await client.query(
                collection_name=self.config.collection_name,
                expr=f"{self.config.id_field} in [ {','.join(vector_ids)} ]",
                output_fields=[ self.config.id_field ],
                partition_names=[ self.config.partition_name ] if self.config.partition_name else None,
            )

            found_ids = { row[self.config.id_field] for row in (queried or []) }
            missing_ids = set(vector_ids) - found_ids
            if missing_ids:
                data = [ item for item in data if item[self.config.id_field] in found_ids ]

        if len(data) > 0:
            result = await client.upsert(
                collection_name=self.config.collection_name,
                data=data,
                partition_name=self.config.partition_name
            )
        else:
            result = { "upsert_count": 0 }

        return { "affected_rows": result["upsert_count"] }

    async def _search(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        query         = await context.render_variable(self.config.query)
        top_k         = await context.render_variable(self.config.top_k)
        metric_type   = await context.render_variable(self.config.metric_type)
        filter        = await context.render_variable(self.config.filter)
        output_fields = await context.render_variable(self.config.output_fields)

        is_single_input: bool = True if not (isinstance(query, list) and query and isinstance(query[0], (list, tuple))) else False
        queries: List[List[float]] = [ query ] if is_single_input else query
        search_params = {}

        if metric_type:
            search_params["metric_type"] = metric_type

        results = await client.search(
            collection_name=self.config.collection_name,
            data=queries,
            filter=filter,
            limit=top_k,
            output_fields=output_fields or None,
            search_params=search_params or None,
            partition_names=[ self.config.partition_name ] if self.config.partition_name else None
        )
        results = [ [ dict(hit) for hit in result ] for result in results ]

        return results[0] if is_single_input else results

    async def _remove(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        vector_id = await context.render_variable(self.config.vector_id)

        is_single_input: bool = True if not isinstance(vector_id, list) else False
        vector_ids: List[Union[int, str]] = [ vector_id ] if is_single_input else vector_id

        result = await client.delete(
            collection_name=self.config.collection_name,
            filter=f"{self.config.id_field} in [ {','.join([ str(id) for id in vector_ids ])} ]",
            partition_name=getattr(self.config, "partition_name", None)
        )

        return { "affected_rows": result["delete_count"] }

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
            db_name=self.config.database_name or "",
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

        if self.config.protocol != "grpc":
            return { "uri": f"{self.config.protocol}://{self.config.host}:{self.config.port}" }
        
        return { "host": self.config.host, "port": self.config.port }
