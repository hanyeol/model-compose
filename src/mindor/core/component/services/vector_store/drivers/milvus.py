from __future__ import annotations
from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from typing import TYPE_CHECKING
from mindor.dsl.schema.component import VectorStoreComponentConfig
from mindor.dsl.schema.action import VectorStoreActionConfig, MilvusVectorStoreActionConfig, VectorStoreActionMethod
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ..base import VectorStoreService, VectorStoreDriver, register_vector_store_service
from ..base import ComponentActionContext

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
        vectors  = await context.render_variable(self.config.vectors)
        ids      = await context.render_variable(self.config.ids)
        metadata = await context.render_variable(self.config.metadata)

        data = []
        for index, vector in enumerate(vectors):
            item = { self.config.vector_field: vector }

            if ids and index < len(ids):
                item.update({ "id": ids[index] })

            if metadata and index < len(metadata):
                item.update(metadata[index])

            data.append(item)

        result = await client.insert(
            collection_name=self.config.collection_name,
            data=data,
            partition_name=self.config.partition_name
        )

        return { "ids": result["ids"], "affected_rows": result["insert_count"] }

    async def _update(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        pass

    async def _search(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        pass

    async def _remove(self, context: ComponentActionContext, client: AsyncMilvusClient) -> Dict[str, Any]:
        pass

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
