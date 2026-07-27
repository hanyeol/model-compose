from __future__ import annotations

from typing import Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.action import GraphStoreActionConfig, GraphStoreActionMethod
from ..base import ComponentActionContext
from ....action.base import ComponentAction

class GraphStoreAction(ComponentAction):
    def __init__(self, config: GraphStoreActionConfig, database: Any):
        self.config: GraphStoreActionConfig = config
        self.database: Any = database

    async def run(self, context: ComponentActionContext) -> Any:
        params = await self._resolve_params(self.config.method, context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(self.config.method, params)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: GraphStoreActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == GraphStoreActionMethod.QUERY:
            query  = await context.render_variable(self.config.query)
            params = await context.render_variable(self.config.params)

            return {
                "query":  query,
                "params": params,
            }

        if method == GraphStoreActionMethod.INSERT:
            nodes         = await context.render_variable(self.config.nodes)
            relationships = await context.render_variable(self.config.relationships)

            return {
                "nodes":         nodes,
                "relationships": relationships,
            }

        if method == GraphStoreActionMethod.UPDATE:
            node_id         = await context.render_variable(self.config.node_id)
            relationship_id = await context.render_variable(self.config.relationship_id)
            properties      = await context.render_variable(self.config.properties)
            labels          = await context.render_variable(self.config.labels)

            return {
                "node_id":         node_id,
                "relationship_id": relationship_id,
                "properties":      properties,
                "labels":          labels,
            }

        if method == GraphStoreActionMethod.DELETE:
            node_id         = await context.render_variable(self.config.node_id)
            relationship_id = await context.render_variable(self.config.relationship_id)
            detach          = await context.render_variable(self.config.detach)

            return {
                "node_id":         node_id,
                "relationship_id": relationship_id,
                "detach":          detach,
            }

        if method == GraphStoreActionMethod.TRAVERSE:
            start_node         = await context.render_variable(self.config.start_node)
            direction          = await context.render_variable(self.config.direction)
            max_depth          = await context.render_variable(self.config.max_depth)
            relationship_types = await context.render_variable(self.config.relationship_types)
            node_labels        = await context.render_variable(self.config.node_labels)

            return {
                "start_node":         start_node,
                "direction":          direction,
                "max_depth":          max_depth,
                "relationship_types": relationship_types,
                "node_labels":        node_labels,
            }

        raise ValueError(f"Unsupported graph action method: {method}")

    async def _dispatch(self, method: GraphStoreActionMethod, params: Dict[str, Any]) -> Any:
        if method == GraphStoreActionMethod.QUERY:
            return await self._query(params)

        if method == GraphStoreActionMethod.INSERT:
            return await self._insert(params)

        if method == GraphStoreActionMethod.UPDATE:
            return await self._update(params)

        if method == GraphStoreActionMethod.DELETE:
            return await self._delete(params)

        if method == GraphStoreActionMethod.TRAVERSE:
            return await self._traverse(params)

        raise ValueError(f"Unsupported graph action method: {method}")

    @abstractmethod
    async def _query(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _insert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _traverse(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass
