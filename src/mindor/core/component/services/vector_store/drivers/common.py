from __future__ import annotations

from typing import Union, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import VectorStoreActionConfig, VectorStoreActionMethod
from ..base import ComponentActionContext
from ....action.base import ComponentAction

class VectorStoreAction(ComponentAction):
    def __init__(self, config: VectorStoreActionConfig, client: Any):
        self.config: VectorStoreActionConfig = config
        self.client: Any = client

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, params)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _dispatch(self, method: VectorStoreActionMethod, params: Dict[str, Any]) -> Any:
        if method == VectorStoreActionMethod.INSERT:
            return await self._insert(params)

        if method == VectorStoreActionMethod.UPDATE:
            return await self._update(params)

        if method == VectorStoreActionMethod.SEARCH:
            return await self._search(params)

        if method == VectorStoreActionMethod.DELETE:
            return await self._delete(params)

        raise ValueError(f"Unsupported vector action method: {method}")

    async def _resolve_params(self, method: VectorStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == VectorStoreActionMethod.INSERT:
            collection = await context.render_variable(self.config.collection)
            vector     = await context.render_variable(self.config.vector)
            vector_id  = await context.render_variable(self.config.vector_id)
            metadata   = await context.render_variable(self.config.metadata)
            batch_size = await context.render_variable(self.config.batch_size)

            return {
                "collection": collection,
                "vector":     vector,
                "vector_id":  vector_id,
                "metadata":   metadata,
                "batch_size": batch_size,
            }

        if method == VectorStoreActionMethod.UPDATE:
            collection = await context.render_variable(self.config.collection)
            vector_id  = await context.render_variable(self.config.vector_id)
            vector     = await context.render_variable(self.config.vector)
            metadata   = await context.render_variable(self.config.metadata)
            batch_size = await context.render_variable(self.config.batch_size)

            return {
                "collection": collection,
                "vector_id":  vector_id,
                "vector":     vector,
                "metadata":   metadata,
                "batch_size": batch_size,
            }

        if method == VectorStoreActionMethod.SEARCH:
            collection    = await context.render_variable(self.config.collection)
            query         = await context.render_variable(self.config.query)
            top_k         = await context.render_variable(self.config.top_k)
            filter        = await context.render_variable(self.config.filter)
            output_fields = await context.render_variable(self.config.output_fields)
            batch_size    = await context.render_variable(self.config.batch_size)

            return {
                "collection":    collection,
                "query":         query,
                "top_k":         top_k,
                "filter":        filter,
                "output_fields": output_fields,
                "batch_size":    batch_size,
            }

        if method == VectorStoreActionMethod.DELETE:
            collection = await context.render_variable(self.config.collection)
            vector_id  = await context.render_variable(self.config.vector_id)
            filter     = await context.render_variable(self.config.filter)
            batch_size = await context.render_variable(self.config.batch_size)

            return {
                "collection": collection,
                "vector_id":  vector_id,
                "filter":     filter,
                "batch_size": batch_size,
            }

        raise ValueError(f"Unsupported vector action method: {method}")

    @abstractmethod
    async def _insert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _search(self, params: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    async def _delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass
